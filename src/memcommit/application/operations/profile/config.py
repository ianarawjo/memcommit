"""Read the process-local MemoryStore profile selection.

This module deliberately does not import :mod:`memcommit.persistence.store`.  The store
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

from memcommit.configuration.workspace import require_workspace_ready, workspace_paths

from memcommit.application.authorization.checkpoint_read_model import (
    CheckpointRead,
    CheckpointReadValueError,
    canonical_checkpoint_reads,
)


PROFILE_REGISTRY_SCHEMA_VERSION = 7
AUTHORING_PROFILE_UID = "00000000-0000-0000-0000-000000000001"
AUTHORING_PROFILE_NAME = "authoring"
STUDY_RUN_PARTICIPANT_SOURCE_KIND = "STUDY_RUN"
STUDY_RUN_AUTHORITY_SOURCE_KIND = "STUDY_RUN_GRANTED_MEMORY"
_PROFILE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
GRANT_RESOURCE_CONTEXT_TREE = "CONTEXT_TREE"
CONTEXT_USES = frozenset(
    {
        "CREATE",
        "READ",
        "EDIT",
        "DELETE",
        "QUERY",
    }
)
GRANT_ENDPOINT_CAPABILITIES = frozenset({"SHARE"})
GRANT_PERMISSIONS = CONTEXT_USES | GRANT_ENDPOINT_CAPABILITIES
LEGACY_GRANT_PERMISSIONS = frozenset(
    {
        "EMBED",
        "DERIVE",
        "COMBINE",
        "EXPORT",
        "ACCEPT_DERIVED",
        "SAVE_BOUND_ANALYSIS",
        "SAVE_ANALYSIS",
        "SESSION_LOG",
    }
)
_GRANT_PERMISSION_ORDER = (
    "CREATE",
    "READ",
    "EDIT",
    "DELETE",
    "QUERY",
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
    root_dir: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "root_dir", str(profile_root_dir(self).resolve()))

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "uid": self.uid,
            "name": self.name,
            "kind": self.kind,
            "root_dir": str(profile_root_dir(self)),
        }
        if self.source is not None:
            result["source"] = self.source
        return result


@dataclass(frozen=True)
class StudyRunIdentity:
    """Validated stable provenance shared by the registered Study members."""

    uid: str
    name: str
    created_at: str
    role: str
    baseline_profile_uid: str
    baseline_profile_name: str
    baseline_sha256: str
    provider_policy_version: str | None = None
    provider_policy_digest: str | None = None


def study_run_identity(profile: ProfileEntry) -> StudyRunIdentity | None:
    """Return current ``init-study`` identity without relying on its name.

    Profile display names may change independently from the Study label. The
    stable Study UID and role in this source record are therefore the durable
    discriminators used by logging and presentation; ``name`` is editable
    display metadata shared by both members.
    """

    source = profile.source
    if not isinstance(source, dict) or source.get("kind") not in {
        STUDY_RUN_PARTICIPANT_SOURCE_KIND,
        STUDY_RUN_AUTHORITY_SOURCE_KIND,
    }:
        return None
    legacy_fields = {
        "kind",
        "study_uid",
        "study_name",
        "created_at",
        "baseline_sha256",
        "baseline_profile_uid",
        "baseline_profile_name",
    }
    pinned_fields = legacy_fields | {
        "provider_policy_version",
        "provider_policy_digest",
    }
    source_fields = frozenset(source)
    if (
        source_fields
        not in {
            frozenset(legacy_fields),
            frozenset(pinned_fields),
        }
        or profile.kind != "MANAGED"
    ):
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
    if (
        not isinstance(baseline_sha256, str)
        or _SHA256.fullmatch(baseline_sha256) is None
    ):
        raise ProfileConfigError("Study baseline digest is invalid.")
    baseline_profile_uid = _canonical_uid(
        source.get("baseline_profile_uid"),
        field="Study baseline Profile uid",
    )
    baseline_profile_name = validate_profile_name(source.get("baseline_profile_name"))
    provider_policy_version = source.get("provider_policy_version")
    provider_policy_digest = source.get("provider_policy_digest")
    if source_fields == pinned_fields:
        if (
            not isinstance(provider_policy_version, str)
            or not provider_policy_version
            or len(provider_policy_version) > 128
        ):
            raise ProfileConfigError("Study provider policy version is invalid.")
        if (
            not isinstance(provider_policy_digest, str)
            or _SHA256.fullmatch(provider_policy_digest) is None
        ):
            raise ProfileConfigError("Study provider policy digest is invalid.")
    else:
        provider_policy_version = None
        provider_policy_digest = None
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
        provider_policy_version=provider_policy_version,
        provider_policy_digest=provider_policy_digest,
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


def canonical_grant_permissions(
    value: object,
    *,
    allow_legacy: bool = False,
) -> tuple[str, ...]:
    """Return a unique, stable permission tuple for one grant."""

    if not isinstance(value, (list, tuple, set, frozenset)) or not value:
        raise ProfileConfigError("Grant permissions must be a non-empty list.")
    normalized: set[str] = set()
    for raw in value:
        if not isinstance(raw, str):
            raise ProfileConfigError("Grant permission is invalid.")
        permission = raw.strip().upper()
        if permission in LEGACY_GRANT_PERMISSIONS:
            if not allow_legacy:
                raise ProfileConfigError(f"Unsupported grant permission: {raw!r}.")
            # A stored legacy registry must remain loadable after the permission
            # vocabulary contracts. SESSION_LOG historically implied QUERY;
            # every other retired capability added no ordinary Context use.
            if permission == "SESSION_LOG":
                normalized.add("QUERY")
            continue
        if permission not in GRANT_PERMISSIONS:
            raise ProfileConfigError(f"Unsupported grant permission: {raw!r}.")
        normalized.add(permission)
    if normalized & {"CREATE", "EDIT", "DELETE"} and "READ" not in normalized:
        raise ProfileConfigError("Create, edit, and delete grants require READ.")
    if not normalized:
        raise ProfileConfigError("Grant permissions contain no supported use.")
    return tuple(item for item in _GRANT_PERMISSION_ORDER if item in normalized)


def validate_grant_permission(value: object) -> str:
    """Validate one permission without applying whole-grant dependencies."""

    if not isinstance(value, str):
        raise ProfileConfigError("Grant permission is invalid.")
    permission = value.strip().upper()
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
    resource_kind: str
    resource_uid: str
    resource_name: str
    permissions: tuple[str, ...]
    contexts: tuple[GrantContextBinding, ...]
    checkpoint_reads: tuple[CheckpointRead, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "revision": self.revision,
            "authority_profile_uid": self.authority_profile_uid,
            "grantee_profile_uid": self.grantee_profile_uid,
            "resource_kind": self.resource_kind,
            "resource_uid": self.resource_uid,
            "resource_name": self.resource_name,
            "permissions": list(self.permissions),
            "contexts": [context.to_dict() for context in self.contexts],
            "checkpoint_reads": [
                checkpoint_read.to_dict() for checkpoint_read in self.checkpoint_reads
            ],
        }


@dataclass(frozen=True)
class GrantPlacement:
    """One grantee-owned name that mounts an authority Grant."""

    grant_uid: str
    grantee_profile_uid: str
    access_name: str

    def to_dict(self) -> dict[str, str]:
        return {
            "grant_uid": self.grant_uid,
            "grantee_profile_uid": self.grantee_profile_uid,
            "access_name": self.access_name,
        }


@dataclass(frozen=True)
class ProfileRegistry:
    """Validated selector state kept outside every MemoryStore."""

    generation: int
    active_uid: str
    profiles: tuple[ProfileEntry, ...]
    grants: tuple[AuthorityGrant, ...] = ()
    grant_placements: tuple[GrantPlacement, ...] = ()

    @property
    def active(self) -> ProfileEntry:
        return next(
            profile for profile in self.profiles if profile.uid == self.active_uid
        )

    def by_name(self, name: str) -> ProfileEntry | None:
        canonical = validate_profile_name(name)
        return next(
            (profile for profile in self.profiles if profile.name == canonical),
            None,
        )

    @property
    def visible_profiles(self) -> tuple[ProfileEntry, ...]:
        """Every registered Profile is live; deletion unregisters its identity."""

        return self.profiles

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": PROFILE_REGISTRY_SCHEMA_VERSION,
            "generation": self.generation,
            "active_uid": self.active_uid,
            "profiles": [profile.to_dict() for profile in self.profiles],
            "grants": [grant.to_dict() for grant in self.grants],
            "grant_placements": [
                placement.to_dict() for placement in self.grant_placements
            ],
        }


def default_store_dir() -> Path:
    """Return the authoring Store within the selected workspace."""

    require_workspace_ready()
    return workspace_paths().workspace_dir / "authoring" / ".mem"


def profile_control_dir() -> Path:
    require_workspace_ready()
    return workspace_paths().workspace_dir / "profiles"


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
    """Represent the default authoring Profile without creating metadata."""

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
        grant_placements=(),
    )


def load_profile_registry() -> ProfileRegistry:
    """Load registered project roots; absence selects the default authoring root."""

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
    if schema_version not in {6, PROFILE_REGISTRY_SCHEMA_VERSION}:
        raise ProfileConfigError("Unsupported profile registry schema version.")
    generation = value.get("generation")
    if (
        not isinstance(generation, int)
        or isinstance(generation, bool)
        or generation < 1
    ):
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
        if set(raw) - {"uid", "name", "kind", "source", "root_dir"}:
            raise ProfileConfigError("Unexpected Profile registry fields.")
        kind = raw.get("kind")
        if kind not in {"AUTHORING", "MANAGED"}:
            raise ProfileConfigError("Profile kind is invalid.")
        source = raw.get("source")
        if source is not None and not isinstance(source, dict):
            raise ProfileConfigError("Profile source provenance is invalid.")
        root = raw.get("root_dir")
        if not isinstance(root, str) or not Path(root).is_absolute() or str(Path(root).resolve()) != root:
            raise ProfileConfigError("Profile root must be a canonical absolute directory.")
        profiles.append(ProfileEntry(uid=uid, name=name, kind=kind, source=source, root_dir=root))

    if len({profile.uid for profile in profiles}) != len(profiles):
        raise ProfileConfigError("Profile uids must be unique.")
    if len({profile.name.casefold() for profile in profiles}) != len(profiles):
        raise ProfileConfigError("Profile names must be unique.")
    authoring = [profile for profile in profiles if profile.kind == "AUTHORING"]
    if schema_version == 6 and len(authoring) != 1:
        raise ProfileConfigError("Legacy Profile registries must contain the fixed authoring Profile.")
    if len(authoring) > 1 or any(profile.uid != AUTHORING_PROFILE_UID or profile.name != AUTHORING_PROFILE_NAME for profile in authoring):
        raise ProfileConfigError("An authoring Profile must retain its fixed identity.")
    if any(profile.kind != "AUTHORING" and (profile.uid == AUTHORING_PROFILE_UID or profile.name.casefold() == AUTHORING_PROFILE_NAME.casefold()) for profile in profiles):
        raise ProfileConfigError("The fixed authoring Profile identity is reserved.")
    active_uid = _canonical_uid(value.get("active_uid"), field="Active profile uid")
    profile_uids = {profile.uid for profile in profiles}
    if active_uid not in profile_uids:
        raise ProfileConfigError("Active profile is not registered.")

    raw_removed_profile_uids = value.get("removed_profile_uids", [])
    if not isinstance(raw_removed_profile_uids, list):
        raise ProfileConfigError("Removed Profile identities must be a list.")
    legacy_removed_uids = tuple(
        _canonical_uid(raw, field="Removed Profile uid")
        for raw in raw_removed_profile_uids
    )
    if len(set(legacy_removed_uids)) != len(legacy_removed_uids):
        raise ProfileConfigError("Removed Profile identities must be unique.")
    if any(uid not in profile_uids for uid in legacy_removed_uids):
        raise ProfileConfigError("Removed Profile identity is not registered.")
    if AUTHORING_PROFILE_UID in legacy_removed_uids:
        raise ProfileConfigError("The fixed authoring Profile cannot be removed.")
    if active_uid in legacy_removed_uids:
        raise ProfileConfigError("The active Profile cannot be removed.")

    # Read prior deletion flags without reserving their names or writing new
    # tombstones. Registry loading never removes files from a project.
    profiles = [
        profile for profile in profiles if profile.uid not in legacy_removed_uids
    ]
    profile_uids = {profile.uid for profile in profiles}
    for index, profile in enumerate(profiles):
        root = profile_root_dir(profile)
        for other in profiles[index + 1:]:
            other_root = profile_root_dir(other)
            if root == other_root or root.is_relative_to(other_root) or other_root.is_relative_to(root):
                raise ProfileConfigError("Registered Profile project roots overlap.")

    raw_grants = value.get("grants", [])
    if not isinstance(raw_grants, list):
        raise ProfileConfigError("Profile grants must be a list.")
    grants: list[AuthorityGrant] = []
    for raw in raw_grants:
        grant_fields = {
            "uid",
            "revision",
            "authority_profile_uid",
            "grantee_profile_uid",
            "resource_kind",
            "resource_uid",
            "resource_name",
            "permissions",
            "contexts",
            "checkpoint_reads",
        }
        if not isinstance(raw, dict) or set(raw) != grant_fields:
            raise ProfileConfigError("Profile grant entry is invalid.")
        revision = raw.get("revision")
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
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
            item.uid == resource_uid and item.name == resource_name for item in contexts
        ):
            raise ProfileConfigError("Grant scope does not contain its root Context.")
        if any(
            item.name != resource_name and not item.name.startswith(resource_name + "/")
            for item in contexts
        ):
            raise ProfileConfigError(
                "Grant scope contains a Context outside its resource tree."
            )
        try:
            checkpoint_reads = canonical_checkpoint_reads(
                raw.get("checkpoint_reads", [])
            )
        except CheckpointReadValueError as error:
            raise ProfileConfigError(str(error)) from error
        context_uids = {context.uid for context in contexts}
        if any(
            checkpoint_read.context_uid not in context_uids
            for checkpoint_read in checkpoint_reads
        ):
            raise ProfileConfigError(
                "Checkpoint read names a Context outside its Grant scope."
            )
        permissions = canonical_grant_permissions(
            raw.get("permissions"),
            allow_legacy=True,
        )
        if checkpoint_reads and "READ" not in permissions:
            raise ProfileConfigError("Checkpoint reads require READ permission.")
        grants.append(
            AuthorityGrant(
                uid=_canonical_uid(raw.get("uid"), field="Grant uid"),
                revision=revision,
                authority_profile_uid=authority_uid,
                grantee_profile_uid=grantee_uid,
                resource_kind=resource_kind,
                resource_uid=resource_uid,
                resource_name=resource_name,
                permissions=permissions,
                contexts=tuple(contexts),
                checkpoint_reads=checkpoint_reads,
            )
        )
    if len({grant.uid for grant in grants}) != len(grants):
        raise ProfileConfigError("Profile grant uids must be unique.")

    raw_placements = value.get("grant_placements", [])
    if not isinstance(raw_placements, list):
        raise ProfileConfigError("Grant placements must be a list.")
    grants_by_uid = {grant.uid: grant for grant in grants}
    grant_placements: list[GrantPlacement] = []
    for raw in raw_placements:
        if not isinstance(raw, dict) or set(raw) != {
            "grant_uid",
            "grantee_profile_uid",
            "access_name",
        }:
            raise ProfileConfigError("Grant placement entry is invalid.")
        grant_uid = _canonical_uid(
            raw.get("grant_uid"),
            field="Grant placement Grant uid",
        )
        grantee_uid = _canonical_uid(
            raw.get("grantee_profile_uid"),
            field="Grant placement grantee Profile uid",
        )
        grant = grants_by_uid.get(grant_uid)
        if grant is None or grant.grantee_profile_uid != grantee_uid:
            raise ProfileConfigError(
                "Grant placement does not match its authority Grant."
            )
        grant_placements.append(
            GrantPlacement(
                grant_uid=grant_uid,
                grantee_profile_uid=grantee_uid,
                access_name=validate_grant_resource_name(raw.get("access_name")),
            )
        )
    if len({placement.grant_uid for placement in grant_placements}) != len(
        grant_placements
    ):
        raise ProfileConfigError("Each Grant must have exactly one placement.")
    if {placement.grant_uid for placement in grant_placements} != set(grants_by_uid):
        raise ProfileConfigError("Every Grant must have exactly one placement.")
    placement_keys = [
        (placement.grantee_profile_uid, placement.access_name.casefold())
        for placement in grant_placements
    ]
    if len(set(placement_keys)) != len(placement_keys):
        raise ProfileConfigError("Grant access names must be unique per Profile.")
    return ProfileRegistry(
        generation=generation,
        active_uid=active_uid,
        profiles=tuple(profiles),
        grants=tuple(grants),
        grant_placements=tuple(grant_placements),
    )


def profile_root_dir(profile: ProfileEntry) -> Path:
    if profile.root_dir is not None:
        return Path(profile.root_dir)
    if profile.kind == "AUTHORING":
        return default_store_dir().parent
    return workspace_paths().workspace_dir / "projects" / profile.uid


def profile_store_dir(profile: ProfileEntry) -> Path:
    """An explicit internal Store root, always below the Profile project."""
    return profile_root_dir(profile) / ".mem"


def active_profile_registry_for_store(
    store_dir: Path,
    *,
    registry: ProfileRegistry | None = None,
) -> ProfileRegistry | None:
    """Return Profile authority only when it owns the supplied Store root."""

    root = store_dir.resolve()
    try:
        value = registry or load_profile_registry()
    except ProfileConfigError:
        if root == default_store_dir().resolve() or root.is_relative_to(
            profile_stores_dir().resolve()
        ):
            raise
        return None
    if root != profile_store_dir(value.active).resolve():
        return None
    return value


def resolve_active_store_dir() -> Path:
    """Resolve the selected Store root for a caller to freeze."""

    registry = load_profile_registry()
    return profile_store_dir(registry.active)
