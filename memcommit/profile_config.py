"""Read the process-local MemoryStore profile selection.

This module deliberately does not import :mod:`memcommit.store`.  The store
imports it while establishing its immutable process-local root, so importing
the two modules in the opposite direction would make profile selection depend
on import order.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import re
import uuid


PROFILE_REGISTRY_SCHEMA_VERSION = 1
AUTHORING_PROFILE_UID = "00000000-0000-0000-0000-000000000001"
AUTHORING_PROFILE_NAME = "authoring"
_PROFILE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")


class ProfileConfigError(RuntimeError):
    """The external profile registry cannot be trusted."""


@dataclass(frozen=True)
class ProfileEntry:
    """One registered whole-store profile."""

    uid: str
    name: str
    kind: str
    source: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "uid": self.uid,
            "name": self.name,
            "kind": self.kind,
        }
        if self.source is not None:
            result["source"] = self.source
        return result


@dataclass(frozen=True)
class ProfileRegistry:
    """Validated selector state kept outside every MemoryStore."""

    generation: int
    active_uid: str
    profiles: tuple[ProfileEntry, ...]

    @property
    def active(self) -> ProfileEntry:
        return next(profile for profile in self.profiles if profile.uid == self.active_uid)

    def by_name(self, name: str) -> ProfileEntry | None:
        canonical = validate_profile_name(name)
        return next(
            (profile for profile in self.profiles if profile.name == canonical),
            None,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": PROFILE_REGISTRY_SCHEMA_VERSION,
            "generation": self.generation,
            "active_uid": self.active_uid,
            "profiles": [profile.to_dict() for profile in self.profiles],
        }


def default_store_dir() -> Path:
    """Return the backward-compatible authoring store location."""

    return Path.home() / ".mem"


def profile_control_dir() -> Path:
    return Path.home() / ".mem-profiles"


def profile_stores_dir() -> Path:
    return profile_control_dir() / "stores"


def profile_registry_file() -> Path:
    return profile_control_dir() / "registry.json"


def profile_registry_lock_file() -> Path:
    return profile_control_dir() / "registry.lock"


def validate_profile_name(value: object) -> str:
    """Return one portable, non-hierarchical profile name."""

    if not isinstance(value, str) or not _PROFILE_NAME.fullmatch(value):
        raise ProfileConfigError(
            "Profile name must be one 1-64 character segment containing only "
            "letters, digits, '.', '_', or '-'."
        )
    if value in {".", ".."} or "/" in value or "\\" in value:
        raise ProfileConfigError("Profile name must not be a path.")
    return value


def _canonical_uid(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ProfileConfigError(f"{field} must be a canonical UUID.")
    try:
        canonical = str(uuid.UUID(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ProfileConfigError(f"{field} must be a canonical UUID.") from error
    if value != canonical:
        raise ProfileConfigError(f"{field} must be a canonical UUID.")
    return canonical


def _reject_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ProfileConfigError(f"Duplicate profile registry key: {key}")
        result[key] = value
    return result


def virtual_authoring_registry() -> ProfileRegistry:
    """Represent legacy operation without creating any profile metadata."""

    return ProfileRegistry(
        generation=0,
        active_uid=AUTHORING_PROFILE_UID,
        profiles=(
            ProfileEntry(
                uid=AUTHORING_PROFILE_UID,
                name=AUTHORING_PROFILE_NAME,
                kind="AUTHORING",
            ),
        ),
    )


def load_profile_registry() -> ProfileRegistry:
    """Load the registry; absence alone means legacy authoring mode."""

    path = profile_registry_file()
    if not path.exists():
        return virtual_authoring_registry()
    if path.is_symlink() or not path.is_file():
        raise ProfileConfigError("Profile registry storage is invalid.")
    try:
        with open(path, encoding="utf-8") as file:
            value = json.load(file, object_pairs_hook=_reject_duplicate_keys)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProfileConfigError("Profile registry is invalid JSON.") from error
    if not isinstance(value, dict):
        raise ProfileConfigError("Profile registry must be a JSON object.")
    if value.get("schema_version") != PROFILE_REGISTRY_SCHEMA_VERSION:
        raise ProfileConfigError("Unsupported profile registry schema version.")
    generation = value.get("generation")
    if not isinstance(generation, int) or isinstance(generation, bool) or generation < 1:
        raise ProfileConfigError("Profile registry generation is invalid.")
    raw_profiles = value.get("profiles")
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raise ProfileConfigError("Profile registry must contain profiles.")

    profiles: list[ProfileEntry] = []
    for raw in raw_profiles:
        if not isinstance(raw, dict):
            raise ProfileConfigError("Profile registry entry is invalid.")
        uid = _canonical_uid(raw.get("uid"), field="Profile uid")
        name = validate_profile_name(raw.get("name"))
        kind = raw.get("kind")
        if kind not in {"AUTHORING", "MANAGED"}:
            raise ProfileConfigError("Profile kind is invalid.")
        source = raw.get("source")
        if source is not None and not isinstance(source, dict):
            raise ProfileConfigError("Profile source provenance is invalid.")
        profiles.append(ProfileEntry(uid=uid, name=name, kind=kind, source=source))

    if len({profile.uid for profile in profiles}) != len(profiles):
        raise ProfileConfigError("Profile uids must be unique.")
    if len({profile.name.casefold() for profile in profiles}) != len(profiles):
        raise ProfileConfigError("Profile names must be unique.")
    authoring = [profile for profile in profiles if profile.kind == "AUTHORING"]
    if authoring != [
        ProfileEntry(
            uid=AUTHORING_PROFILE_UID,
            name=AUTHORING_PROFILE_NAME,
            kind="AUTHORING",
        )
    ]:
        raise ProfileConfigError(
            "Profile registry must contain exactly the fixed authoring profile."
        )
    active_uid = _canonical_uid(value.get("active_uid"), field="Active profile uid")
    if active_uid not in {profile.uid for profile in profiles}:
        raise ProfileConfigError("Active profile is not registered.")
    return ProfileRegistry(
        generation=generation,
        active_uid=active_uid,
        profiles=tuple(profiles),
    )


def profile_store_dir(profile: ProfileEntry) -> Path:
    """Map a validated registry entry to its non-user-controlled root."""

    if profile.kind == "AUTHORING":
        return default_store_dir()
    return profile_stores_dir() / profile.uid


def resolve_active_store_dir() -> Path:
    """Freeze the selected store root for the importing process."""

    registry = load_profile_registry()
    return profile_store_dir(registry.active)
