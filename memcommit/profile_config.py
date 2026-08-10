"""Read the process-local MemoryStore profile selection.

This module deliberately does not import :mod:`memcommit.store`.  The store
imports it while establishing its immutable process-local root, so importing
the two modules in the opposite direction would make profile selection depend
on import order.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
import uuid


PROFILE_REGISTRY_SCHEMA_VERSION = 2
LEGACY_PROFILE_REGISTRY_SCHEMA_VERSION = 1
AUTHORING_PROFILE_UID = "00000000-0000-0000-0000-000000000001"
AUTHORING_PROFILE_NAME = "authoring"
STUDY_RUN_PARTICIPANT_SOURCE_KIND = "STUDY_RUN"
STUDY_RUN_AUTHORITY_SOURCE_KIND = "STUDY_RUN_GRANTED_MEMORY"
_PROFILE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
GRANT_RESOURCE_CONTEXT_TREE = "CONTEXT_TREE"
GRANT_PERMISSIONS = frozenset(
    {
        "CREATE",
        "READ",
        "UPDATE",
        "DELETE",
        "QUERY",
        "SESSION_LOG",
        "DERIVE",
        "COMBINE",
        "EXPORT",
        "ACCEPT_DERIVED",
        "SAVE_BOUND_ANALYSIS",
        "SAVE_ANALYSIS",
        "SHARE",
    }
)
_GRANT_PERMISSION_ORDER = (
    "CREATE",
    "READ",
    "UPDATE",
    "DELETE",
    "QUERY",
    "SESSION_LOG",
    "DERIVE",
    "COMBINE",
    "EXPORT",
    "ACCEPT_DERIVED",
    "SAVE_BOUND_ANALYSIS",
    "SAVE_ANALYSIS",
    "SHARE",
)


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
class StudyRunIdentity:
    """Validated immutable provenance shared by one current Study pair."""

    uid: str
    name: str
    created_at: str
    role: str
    baseline_profile_uid: str
    baseline_profile_name: str
    baseline_sha256: str


def study_run_identity(profile: ProfileEntry) -> StudyRunIdentity | None:
    """Return current ``init-study`` identity without relying on its name.

    Profile display names may change independently from provenance.  The
    source record is therefore the only durable Study discriminator used by
    logging and presentation.
    """

    source = profile.source
    if not isinstance(source, dict) or source.get("kind") not in {
        STUDY_RUN_PARTICIPANT_SOURCE_KIND,
        STUDY_RUN_AUTHORITY_SOURCE_KIND,
    }:
        return None
    expected_fields = {
        "kind",
        "study_uid",
        "study_name",
        "created_at",
        "baseline_sha256",
        "baseline_profile_uid",
        "baseline_profile_name",
    }
    if set(source) != expected_fields or profile.kind != "MANAGED":
        raise ProfileConfigError("Study run Profile provenance is invalid.")
    study_uid = _canonical_uid(source.get("study_uid"), field="Study uid")
    study_name = validate_profile_name(source.get("study_name"))
    created_at = source.get("created_at")
    try:
        parsed_created_at = datetime.fromisoformat(created_at)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise ProfileConfigError("Study creation timestamp is invalid.") from error
    if parsed_created_at.tzinfo is None or parsed_created_at.utcoffset() is None:
        raise ProfileConfigError("Study creation timestamp must include a timezone.")
    baseline_sha256 = source.get("baseline_sha256")
    if not isinstance(baseline_sha256, str) or _SHA256.fullmatch(baseline_sha256) is None:
        raise ProfileConfigError("Study baseline digest is invalid.")
    baseline_profile_uid = _canonical_uid(
        source.get("baseline_profile_uid"),
        field="Study baseline Profile uid",
    )
    baseline_profile_name = validate_profile_name(source.get("baseline_profile_name"))
    role = (
        "PARTICIPANT"
        if source.get("kind") == STUDY_RUN_PARTICIPANT_SOURCE_KIND
        else "GRANTED_MEMORY"
    )
    return StudyRunIdentity(
        uid=study_uid,
        name=study_name,
        created_at=created_at,  # type: ignore[arg-type]
        role=role,
        baseline_profile_uid=baseline_profile_uid,
        baseline_profile_name=baseline_profile_name,
        baseline_sha256=baseline_sha256,
    )


def validate_grant_resource_name(value: object) -> str:
    """Validate one canonical Context-tree locator without importing store."""

    if not isinstance(value, str) or not value:
        raise ProfileConfigError("Grant resource name must be non-empty.")
    if "\\" in value or ":" in value:
        raise ProfileConfigError("Grant resource name is invalid.")
    parts = value.split("/")
    if any(
        not part
        or part in {".", ".."}
        or part.casefold() in {"context.json", "checkpoints"}
        for part in parts
    ):
        raise ProfileConfigError("Grant resource name is invalid.")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ProfileConfigError("Grant resource name is invalid.")
    return value


def canonical_grant_permissions(value: object) -> tuple[str, ...]:
    """Return a unique, stable permission tuple for one grant."""

    if not isinstance(value, (list, tuple, set, frozenset)) or not value:
        raise ProfileConfigError("Grant permissions must be a non-empty list.")
    normalized: set[str] = set()
    for raw in value:
        if not isinstance(raw, str):
            raise ProfileConfigError("Grant permission is invalid.")
        permission = raw.strip().upper()
        if permission == "EDIT":
            permission = "UPDATE"
        if permission not in GRANT_PERMISSIONS:
            raise ProfileConfigError(f"Unsupported grant permission: {raw!r}.")
        normalized.add(permission)
    if "SESSION_LOG" in normalized and "QUERY" not in normalized:
        raise ProfileConfigError("SESSION_LOG requires QUERY permission.")
    if normalized & {"DERIVE", "ACCEPT_DERIVED"} and "READ" not in normalized:
        raise ProfileConfigError(
            "Derive and accept-derived grants require READ permission."
        )
    if (
        normalized
        & {"COMBINE", "EXPORT", "SAVE_BOUND_ANALYSIS", "SAVE_ANALYSIS"}
        and "DERIVE" not in normalized
    ):
        raise ProfileConfigError(
            "Combine, export, and analysis-save grants require DERIVE permission."
        )
    if "ACCEPT_DERIVED" in normalized and not normalized & {
        "CREATE",
        "UPDATE",
        "DELETE",
    }:
        raise ProfileConfigError(
            "ACCEPT_DERIVED requires a create, update, or delete permission."
        )
    if normalized & {"CREATE", "UPDATE", "DELETE"} and "READ" not in normalized:
        raise ProfileConfigError("Create, update, and delete grants require READ.")
    return tuple(item for item in _GRANT_PERMISSION_ORDER if item in normalized)


def validate_grant_permission(value: object) -> str:
    """Validate one permission without applying whole-grant dependencies."""

    if not isinstance(value, str):
        raise ProfileConfigError("Grant permission is invalid.")
    permission = value.strip().upper()
    if permission == "EDIT":
        permission = "UPDATE"
    if permission not in GRANT_PERMISSIONS:
        raise ProfileConfigError(f"Unsupported grant permission: {value!r}.")
    return permission


@dataclass(frozen=True)
class GrantContextBinding:
    """One exact authority Context admitted to a frozen grant scope."""

    uid: str
    name: str

    def to_dict(self) -> dict[str, str]:
        return {"uid": self.uid, "name": self.name}


@dataclass(frozen=True)
class AuthorityGrant:
    """One authority-owned Context view granted to another Profile."""

    uid: str
    revision: int
    authority_profile_uid: str
    grantee_profile_uid: str
    attachment_context_uid: str
    attachment_context_name: str
    resource_kind: str
    resource_uid: str
    resource_name: str
    public_name: str
    permissions: tuple[str, ...]
    contexts: tuple[GrantContextBinding, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "revision": self.revision,
            "authority_profile_uid": self.authority_profile_uid,
            "grantee_profile_uid": self.grantee_profile_uid,
            "attachment_context_uid": self.attachment_context_uid,
            "attachment_context_name": self.attachment_context_name,
            "resource_kind": self.resource_kind,
            "resource_uid": self.resource_uid,
            "resource_name": self.resource_name,
            "public_name": self.public_name,
            "permissions": list(self.permissions),
            "contexts": [context.to_dict() for context in self.contexts],
        }


@dataclass(frozen=True)
class ProfileRegistry:
    """Validated selector state kept outside every MemoryStore."""

    generation: int
    active_uid: str
    profiles: tuple[ProfileEntry, ...]
    grants: tuple[AuthorityGrant, ...] = ()

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
            "grants": [grant.to_dict() for grant in self.grants],
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
        grants=(),
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
    schema_version = value.get("schema_version")
    if schema_version not in {
        LEGACY_PROFILE_REGISTRY_SCHEMA_VERSION,
        PROFILE_REGISTRY_SCHEMA_VERSION,
    }:
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
    profile_uids = {profile.uid for profile in profiles}
    if active_uid not in profile_uids:
        raise ProfileConfigError("Active profile is not registered.")

    raw_grants = value.get("grants", [])
    if schema_version == LEGACY_PROFILE_REGISTRY_SCHEMA_VERSION:
        if "grants" in value:
            raise ProfileConfigError("Legacy profile registry cannot contain grants.")
        raw_grants = []
    if not isinstance(raw_grants, list):
        raise ProfileConfigError("Profile grants must be a list.")
    grants: list[AuthorityGrant] = []
    for raw in raw_grants:
        if not isinstance(raw, dict) or set(raw) != {
            "uid",
            "revision",
            "authority_profile_uid",
            "grantee_profile_uid",
            "attachment_context_uid",
            "attachment_context_name",
            "resource_kind",
            "resource_uid",
            "resource_name",
            "public_name",
            "permissions",
            "contexts",
        }:
            raise ProfileConfigError("Profile grant entry is invalid.")
        revision = raw.get("revision")
        if (
            not isinstance(revision, int)
            or isinstance(revision, bool)
            or revision < 1
        ):
            raise ProfileConfigError("Profile grant revision is invalid.")
        authority_uid = _canonical_uid(
            raw.get("authority_profile_uid"),
            field="Grant authority Profile uid",
        )
        grantee_uid = _canonical_uid(
            raw.get("grantee_profile_uid"),
            field="Grant grantee Profile uid",
        )
        if authority_uid not in profile_uids or grantee_uid not in profile_uids:
            raise ProfileConfigError("Profile grant names an unregistered Profile.")
        if authority_uid == grantee_uid:
            raise ProfileConfigError("A Profile cannot grant a view to itself.")
        resource_kind = raw.get("resource_kind")
        if resource_kind != GRANT_RESOURCE_CONTEXT_TREE:
            raise ProfileConfigError("Profile grant resource kind is invalid.")
        raw_contexts = raw.get("contexts")
        if not isinstance(raw_contexts, list) or not raw_contexts:
            raise ProfileConfigError("Profile grant Context scope is invalid.")
        contexts: list[GrantContextBinding] = []
        for raw_context in raw_contexts:
            if not isinstance(raw_context, dict) or set(raw_context) != {
                "uid",
                "name",
            }:
                raise ProfileConfigError("Profile grant Context binding is invalid.")
            contexts.append(
                GrantContextBinding(
                    uid=_canonical_uid(
                        raw_context.get("uid"),
                        field="Grant Context uid",
                    ),
                    name=validate_grant_resource_name(raw_context.get("name")),
                )
            )
        if len({item.uid for item in contexts}) != len(contexts) or len(
            {item.name for item in contexts}
        ) != len(contexts):
            raise ProfileConfigError("Profile grant Context scope is duplicated.")
        resource_uid = _canonical_uid(
            raw.get("resource_uid"),
            field="Grant resource uid",
        )
        resource_name = validate_grant_resource_name(raw.get("resource_name"))
        if not any(
            item.uid == resource_uid and item.name == resource_name
            for item in contexts
        ):
            raise ProfileConfigError("Grant scope does not contain its root Context.")
        if any(
            item.name != resource_name
            and not item.name.startswith(resource_name + "/")
            for item in contexts
        ):
            raise ProfileConfigError(
                "Grant scope contains a Context outside its resource tree."
            )
        grants.append(
            AuthorityGrant(
                uid=_canonical_uid(raw.get("uid"), field="Grant uid"),
                revision=revision,
                authority_profile_uid=authority_uid,
                grantee_profile_uid=grantee_uid,
                attachment_context_uid=_canonical_uid(
                    raw.get("attachment_context_uid"),
                    field="Grant attachment Context uid",
                ),
                attachment_context_name=validate_grant_resource_name(
                    raw.get("attachment_context_name")
                ),
                resource_kind=resource_kind,
                resource_uid=resource_uid,
                resource_name=resource_name,
                public_name=validate_grant_resource_name(raw.get("public_name")),
                permissions=canonical_grant_permissions(raw.get("permissions")),
                contexts=tuple(contexts),
            )
        )
    if len({grant.uid for grant in grants}) != len(grants):
        raise ProfileConfigError("Profile grant uids must be unique.")
    public_keys = [
        (
            grant.grantee_profile_uid,
            grant.attachment_context_uid,
            grant.public_name.casefold(),
        )
        for grant in grants
    ]
    if len(set(public_keys)) != len(public_keys):
        raise ProfileConfigError("Granted public view names must be unique per Profile.")
    return ProfileRegistry(
        generation=generation,
        active_uid=active_uid,
        profiles=tuple(profiles),
        grants=tuple(grants),
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
