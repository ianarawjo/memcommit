"""Atomically publish Profiles and Grants created by init-study."""

from __future__ import annotations

import os
import shutil
import uuid
from dataclasses import replace
from pathlib import Path

from memcommit.application.operations.init_study.model import StudyInitializationResult
from memcommit.application.operations.profile.config import (
    GRANT_RESOURCE_CONTEXT_TREE,
    STUDY_RUN_AUTHORITY_SOURCE_KIND,
    STUDY_RUN_PARTICIPANT_SOURCE_KIND,
    AuthorityGrant,
    GrantPlacement,
    ProfileConfigError,
    ProfileEntry,
    ProfileRegistry,
    canonical_grant_permissions,
    load_profile_registry,
    profile_store_dir,
    profile_stores_dir,
    validate_grant_resource_name,
)
from memcommit.application.operations.profile.model._storage import (
    ProfileError,
    StoreInspection,
    _context_records,
    _inspection_with_grants,
    _write_registry,
    inspect_store,
)
from memcommit.application.operations.profile.model.grants import _grant_scope
from memcommit.application.operations.profile.model.study import _STUDY_TASKS
from memcommit.core.context import Context, Memory

from .composition import _compose_study_run_pair
from .model import (
    StudyImportResult,
    _study_run_authority_profile_name,
    _StudyTaskPackage,
)
from .package import (
    _expected_study_grant_uid,
    _study_manifest_context,
    _study_uuid,
)

_STUDY_RUN_SOURCE_KIND = STUDY_RUN_PARTICIPANT_SOURCE_KIND


_STUDY_RUN_GRANTED_SOURCE_KIND = STUDY_RUN_AUTHORITY_SOURCE_KIND


def _materialize_study_grants(
    packages: dict[int, _StudyTaskPackage],
    profiles_by_name: dict[str, ProfileEntry],
    staged_roots: dict[str, Path],
) -> tuple[tuple[AuthorityGrant, ...], tuple[GrantPlacement, ...]]:
    """Resolve templates only after every imported Profile has a local UID."""

    contexts_by_profile = {
        name: _context_records(root)[0] for name, root in staged_roots.items()
    }
    sources_by_name = {
        source.name: source
        for package in packages.values()
        for source in package.profiles
    }
    all_grants: list[AuthorityGrant] = []
    all_placements: list[GrantPlacement] = []

    for task in _STUDY_TASKS:
        package = packages[task]
        if package.schema_version == 1:
            continue
        raw_by_key: dict[str, dict[str, object]] = {}
        ordered_keys: list[str] = []
        for raw in package.grant_templates:
            key = raw.get("key")
            if not isinstance(key, str) or not key or key in raw_by_key:
                raise ProfileError(f"Task {task} grant template key is invalid.")
            raw_by_key[key] = raw
            ordered_keys.append(key)

        resolved: dict[str, AuthorityGrant] = {}
        placements_by_key: dict[str, GrantPlacement] = {}
        resolving: set[str] = set()

        def resolve(key: str) -> AuthorityGrant:
            existing = resolved.get(key)
            if existing is not None:
                return existing
            raw = raw_by_key.get(key)
            if raw is None:
                raise ProfileError(f"Task {task} grant parent does not exist.")
            if key in resolving:
                raise ProfileError(f"Task {task} grant attachments contain a cycle.")
            resolving.add(key)
            try:
                expected_fields = {
                    "schema_version",
                    "key",
                    "grant_uid",
                    "authority_profile",
                    "grantee_profile",
                    "authority_context",
                    "attachment",
                    "public_name",
                    "permissions",
                    "recursive",
                    "excluded_contexts",
                }
                if "provider" in raw:
                    expected_fields.add("provider")
                if set(raw) != expected_fields or raw.get("schema_version") != 1:
                    raise ProfileError(f"Task {task} grant template is invalid.")
                authority_name = raw.get("authority_profile")
                grantee_name = raw.get("grantee_profile")
                if (
                    not isinstance(authority_name, str)
                    or not isinstance(grantee_name, str)
                    or authority_name not in profiles_by_name
                    or grantee_name not in profiles_by_name
                    or sources_by_name.get(authority_name) is None
                    or sources_by_name.get(grantee_name) is None
                    or sources_by_name[authority_name].role != "AUTHORITY"
                    or sources_by_name[grantee_name].role != "TASK"
                    or authority_name
                    not in {source.name for source in package.profiles}
                    or grantee_name not in {source.name for source in package.profiles}
                ):
                    raise ProfileError(f"Task {task} grant Profile binding is invalid.")
                authority = profiles_by_name[authority_name]
                grantee = profiles_by_name[grantee_name]
                authority_contexts = contexts_by_profile[authority_name]
                grantee_contexts = contexts_by_profile[grantee_name]
                resource = _study_manifest_context(
                    raw.get("authority_context"),
                    contexts=authority_contexts,
                    label=f"Task {task} grant authority Context",
                )

                try:
                    permissions = canonical_grant_permissions(raw.get("permissions"))
                    public_component = validate_grant_resource_name(
                        raw.get("public_name")
                    )
                except (ProfileConfigError, ValueError) as error:
                    raise ProfileError(
                        f"Task {task} grant permissions or public name are invalid."
                    ) from error
                provider = raw.get("provider")
                if "QUERY" in permissions:
                    if not isinstance(provider, str) or not provider:
                        raise ProfileError(
                            f"Task {task} QUERY grant provider is invalid."
                        )
                elif "provider" in raw:
                    raise ProfileError(
                        f"Task {task} non-QUERY grant cannot declare a provider."
                    )

                grant_uid = _study_uuid(
                    raw.get("grant_uid"),
                    label=f"Task {task} grant uid",
                )
                if grant_uid != _expected_study_grant_uid(task, key):
                    raise ProfileError(
                        f"Task {task} grant uid is not deterministic for its key."
                    )

                attachment = raw.get("attachment")
                if not isinstance(attachment, dict):
                    raise ProfileError(f"Task {task} grant attachment is invalid.")
                attachment_kind = attachment.get("kind")
                if attachment_kind == "GRANTEE_CONTEXT":
                    if set(attachment) != {"kind", "context"}:
                        raise ProfileError(
                            f"Task {task} grantee attachment is invalid."
                        )
                    _study_manifest_context(
                        attachment.get("context"),
                        contexts=grantee_contexts,
                        label=f"Task {task} grant attachment Context",
                    )
                    access_name = public_component
                elif attachment_kind == "GRANT_VIEW":
                    if set(attachment) != {"kind", "grant_key", "grant_uid"}:
                        raise ProfileError(
                            f"Task {task} nested grant attachment is invalid."
                        )
                    parent_key = attachment.get("grant_key")
                    if not isinstance(parent_key, str):
                        raise ProfileError(
                            f"Task {task} nested grant parent is invalid."
                        )
                    parent = resolve(parent_key)
                    parent_uid = _study_uuid(
                        attachment.get("grant_uid"),
                        label=f"Task {task} parent grant uid",
                    )
                    if (
                        parent_uid != parent.uid
                        or parent.grantee_profile_uid != grantee.uid
                        or parent.authority_profile_uid != authority.uid
                        or (
                            resource.name != parent.resource_name
                            and not resource.name.startswith(parent.resource_name + "/")
                        )
                    ):
                        raise ProfileError(
                            f"Task {task} nested grant parent binding is invalid."
                        )
                    parent_placement = placements_by_key[parent_key]
                    access_name = (
                        f"{parent_placement.access_name}/{public_component}"
                    )
                else:
                    raise ProfileError(f"Task {task} grant attachment is invalid.")

                recursive = raw.get("recursive")
                raw_exclusions = raw.get("excluded_contexts")
                if not isinstance(recursive, bool) or not isinstance(
                    raw_exclusions, list
                ):
                    raise ProfileError(f"Task {task} grant scope is invalid.")
                exclusions: list[Context] = []
                for raw_exclusion in raw_exclusions:
                    exclusion = _study_manifest_context(
                        raw_exclusion,
                        contexts=authority_contexts,
                        label=f"Task {task} grant exclusion",
                    )
                    if not exclusion.name.startswith(resource.name + "/"):
                        raise ProfileError(
                            f"Task {task} grant exclusion is outside its resource."
                        )
                    exclusions.append(exclusion)
                if len({item.uid for item in exclusions}) != len(exclusions):
                    raise ProfileError(f"Task {task} grant exclusions are duplicated.")
                scope = _grant_scope(
                    authority_contexts,
                    resource.name,
                    recursive=recursive,
                )
                if exclusions and not recursive:
                    raise ProfileError(
                        f"Task {task} non-recursive grant cannot have exclusions."
                    )
                scope = tuple(
                    binding
                    for binding in scope
                    if not any(
                        binding.name == exclusion.name
                        or binding.name.startswith(exclusion.name + "/")
                        for exclusion in exclusions
                    )
                )
                if not scope or scope[0].uid != resource.uid:
                    raise ProfileError(f"Task {task} grant root was excluded.")
                grant = AuthorityGrant(
                    uid=grant_uid,
                    revision=1,
                    authority_profile_uid=authority.uid,
                    grantee_profile_uid=grantee.uid,
                    resource_kind=GRANT_RESOURCE_CONTEXT_TREE,
                    resource_uid=resource.uid,
                    resource_name=resource.name,
                    permissions=permissions,
                    contexts=scope,
                )
                placements_by_key[key] = GrantPlacement(
                    grant_uid=grant.uid,
                    grantee_profile_uid=grantee.uid,
                    access_name=access_name,
                )
                resolved[key] = grant
                return grant
            finally:
                resolving.discard(key)

        package_grants = tuple(resolve(key) for key in ordered_keys)
        package_placements = tuple(placements_by_key[key] for key in ordered_keys)
        public_keys: set[tuple[str, str]] = set()
        for grant, placement in zip(
            package_grants,
            package_placements,
            strict=True,
        ):
            public_key = (
                grant.grantee_profile_uid,
                placement.access_name.casefold(),
            )
            if public_key in public_keys:
                raise ProfileError(f"Task {task} grant public names are duplicated.")
            public_keys.add(public_key)
            grantee_name = next(
                name
                for name, profile in profiles_by_name.items()
                if profile.uid == grant.grantee_profile_uid
            )
            for local_name in contexts_by_profile[grantee_name]:
                if local_name == placement.access_name or local_name.startswith(
                    placement.access_name + "/"
                ):
                    raise ProfileError(
                        f"Task {task} granted view overlaps a local Context."
                    )

        authority_names_by_uid = {
            profile.uid: name for name, profile in profiles_by_name.items()
        }
        query_memories: set[tuple[str, str]] = set()
        for grant in package_grants:
            if "QUERY" not in grant.permissions:
                continue
            authority_name = authority_names_by_uid[grant.authority_profile_uid]
            for binding in grant.contexts:
                context = contexts_by_profile[authority_name][binding.name]
                query_memories.update(
                    (grant.authority_profile_uid, item.uid)
                    for item in context.iter_items()
                    if isinstance(item, Memory)
                )
        if len(query_memories) != package.query_view_count:
            raise ProfileError(f"Task {task} query view count is inconsistent.")
        all_grants.extend(package_grants)
        all_placements.extend(package_placements)

    if len({grant.uid for grant in all_grants}) != len(all_grants):
        raise ProfileError("Study grant uids are duplicated across task packages.")
    return tuple(all_grants), tuple(all_placements)


def _publish_study_profile_batch(
    registry: ProfileRegistry,
    packages: dict[int, _StudyTaskPackage],
    profiles_by_source_name: dict[str, ProfileEntry],
    *,
    batch_label: str,
    grant_uid_namespace: str | None = None,
) -> StudyImportResult:
    """Publish a prepared task/authority topology under one registry lock."""

    # This private legacy publication path remains import-compatible while its
    # clean-copy primitive is owned by the public mem import operation.
    from memcommit.application.operations.resource_import.profile import (
        _copy_store_baseline,
    )

    sources = tuple(
        source for task in _STUDY_TASKS for source in packages[task].profiles
    )
    if set(profiles_by_source_name) != {source.name for source in sources}:
        raise ProfileError("Study Profile allocation does not match its manifests.")
    profiles = tuple(profiles_by_source_name[source.name] for source in sources)
    if len({profile.uid for profile in profiles}) != len(profiles):
        raise ProfileError("Study Profile uids must be unique.")
    batch = profile_stores_dir() / f".{batch_label}-{uuid.uuid4().hex}"
    batch.mkdir()
    inspections: list[StoreInspection] = []
    published: list[tuple[Path, Path]] = []
    committed = False
    try:
        staged_roots: dict[str, Path] = {}
        for source, profile in zip(sources, profiles, strict=True):
            staging = batch / profile.uid
            provenance = profile.source or {}
            baseline_digest = provenance.get("baseline_sha256")
            inspections.append(
                _copy_store_baseline(
                    source.store,
                    staging,
                    expected_digest=(
                        baseline_digest if isinstance(baseline_digest, str) else None
                    ),
                )
            )
            staged_roots[source.name] = staging

        grants, grant_placements = _materialize_study_grants(
            packages,
            profiles_by_source_name,
            staged_roots,
        )
        if grant_uid_namespace is not None:
            try:
                namespace = uuid.UUID(grant_uid_namespace)
            except (AttributeError, TypeError, ValueError) as error:
                raise ProfileError("Study grant namespace is invalid.") from error
            # Bundle grant UIDs are deterministic fixture identities. Each
            # Study needs distinct registry identities so repeated runs can
            # preserve the same topology without colliding with one another.
            replacement_uids = {
                grant.uid: str(uuid.uuid5(namespace, grant.uid))
                for grant in grants
            }
            grants = tuple(
                replace(grant, uid=replacement_uids[grant.uid])
                for grant in grants
            )
            grant_placements = tuple(
                replace(
                    placement,
                    grant_uid=replacement_uids[placement.grant_uid],
                )
                for placement in grant_placements
            )
        existing_grant_uids = {grant.uid for grant in registry.grants}
        conflicts = [grant.uid for grant in grants if grant.uid in existing_grant_uids]
        if conflicts:
            raise ProfileError(
                "Study grants already exist: " + ", ".join(uid[:8] for uid in conflicts)
            )
        updated = ProfileRegistry(
            generation=max(1, registry.generation + 1),
            active_uid=registry.active_uid,
            profiles=(*registry.profiles, *profiles),
            grants=(*registry.grants, *grants),
            removed_profile_uids=registry.removed_profile_uids,
            grant_placements=(*registry.grant_placements, *grant_placements),
        )
        cache = {
            profile.uid: inspection
            for profile, inspection in zip(profiles, inspections, strict=True)
        }
        grant_aware = tuple(
            _inspection_with_grants(
                updated,
                profile,
                inspection,
                cache=cache,
            )
            for profile, inspection in zip(profiles, inspections, strict=True)
        )

        destinations = tuple(profile_store_dir(profile) for profile in profiles)
        if any(
            destination.exists() or destination.is_symlink()
            for destination in destinations
        ):
            raise ProfileError("Managed profile destination is occupied.")
        for profile in profiles:
            source = batch / profile.uid
            destination = profile_store_dir(profile)
            os.replace(source, destination)
            published.append((destination, source))
        _write_registry(updated)
        committed = True
        final_inspections = tuple(
            replace(inspection, root=profile_store_dir(profile))
            for profile, inspection in zip(profiles, grant_aware, strict=True)
        )
        return StudyImportResult(profiles, final_inspections)
    except BaseException:
        # First-generation cache work can run for minutes. Cancellation must
        # roll the already-moved private stores back just like provider failure
        # instead of leaving unregistered run directories behind.
        if not committed:
            for destination, source in reversed(published):
                if destination.exists() and not source.exists():
                    os.replace(destination, source)
            published.clear()
        raise
    finally:
        if batch.exists() and not batch.is_symlink():
            shutil.rmtree(batch)


def _publish_study_run_pair(
    registry: ProfileRegistry,
    *,
    baseline: ProfileEntry,
    packages: dict[int, _StudyTaskPackage],
    study_name: str,
    study_uid: str,
    created_at: str,
    baseline_digest: str,
    provider_policy_version: str,
    provider_policy_digest: str,
    scenario_id: str = "legacy",
) -> StudyInitializationResult:
    """Publish the run's two stores and grants as one registry transaction."""

    authority_name = _study_run_authority_profile_name(study_name)
    requested_names = {study_name.casefold(), authority_name.casefold()}
    conflicts = [
        profile.name
        for profile in registry.profiles
        if profile.name.casefold() in requested_names
    ]
    if conflicts:
        raise ProfileError(f"Profile {conflicts[0]!r} already exists.")

    common_source: dict[str, object] = {
        "study_uid": study_uid,
        "study_name": study_name,
        "created_at": created_at,
        "baseline_sha256": baseline_digest,
        "baseline_profile_uid": baseline.uid,
        "baseline_profile_name": baseline.name,
        "provider_policy_version": provider_policy_version,
        "provider_policy_digest": provider_policy_digest,
    }
    participant = ProfileEntry(
        uid=str(uuid.uuid4()),
        name=study_name,
        kind="MANAGED",
        source={"kind": _STUDY_RUN_SOURCE_KIND, **common_source},
    )
    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name=authority_name,
        kind="MANAGED",
        source={"kind": _STUDY_RUN_GRANTED_SOURCE_KIND, **common_source},
    )
    batch = profile_stores_dir() / f".{study_name}.study-run-{uuid.uuid4().hex}"
    batch.mkdir()
    participant_staging = batch / participant.uid
    authority_staging = batch / authority.uid
    published: list[tuple[Path, Path]] = []
    committed = False
    try:
        merged = _compose_study_run_pair(
            packages,
            participant_root=participant_staging,
            authority_root=authority_staging,
        )
        profiles_by_name: dict[str, ProfileEntry] = {}
        roots_by_name: dict[str, Path] = {}
        for package in merged.values():
            for source in package.profiles:
                target = authority if source.role == "AUTHORITY" else participant
                profiles_by_name[source.name] = target
                roots_by_name[source.name] = source.store
        grants, grant_placements = _materialize_study_grants(
            merged,
            profiles_by_name,
            roots_by_name,
        )
        namespace = uuid.UUID(study_uid)
        replacement_uids = {
            grant.uid: str(uuid.uuid5(namespace, grant.uid))
            for grant in grants
        }
        grants = tuple(
            replace(grant, uid=replacement_uids[grant.uid])
            for grant in grants
        )
        grant_placements = tuple(
            replace(
                placement,
                grant_uid=replacement_uids[placement.grant_uid],
            )
            for placement in grant_placements
        )
        existing_grant_uids = {grant.uid for grant in registry.grants}
        if any(grant.uid in existing_grant_uids for grant in grants):
            raise ProfileError("Study grant identity already exists.")

        participant_inspection = inspect_store(participant_staging)
        authority_inspection = inspect_store(authority_staging)
        updated = ProfileRegistry(
            generation=max(1, registry.generation + 1),
            # init-study mirrors init: the complete participant/authority pair
            # and grants become visible in the same generation that selects
            # the participant side. The authority Profile is never selected.
            active_uid=participant.uid,
            profiles=(*registry.profiles, participant, authority),
            grants=(*registry.grants, *grants),
            removed_profile_uids=registry.removed_profile_uids,
            grant_placements=(*registry.grant_placements, *grant_placements),
        )
        participant_inspection = _inspection_with_grants(
            updated,
            participant,
            participant_inspection,
            cache={authority.uid: authority_inspection},
        )

        for profile, source in (
            (participant, participant_staging),
            (authority, authority_staging),
        ):
            destination = profile_store_dir(profile)
            if destination.exists() or destination.is_symlink():
                raise ProfileError("Managed profile destination is occupied.")
            os.replace(source, destination)
            published.append((destination, source))
        try:
            _write_registry(updated)
        except Exception as error:
            try:
                replacement_is_visible = load_profile_registry() == updated
            except (OSError, ProfileConfigError, ValueError):
                replacement_is_visible = False
            if replacement_is_visible:
                # A post-replace fsync failure may still leave the complete
                # pair and grant generation visible. Keep both stores so that
                # the registry never points at missing run data.
                committed = True
                raise ProfileError(
                    f"Study run {study_name!r} was published, but registry "
                    "durability could not be confirmed; it remains registered."
                ) from error
            raise
        committed = True
        return StudyInitializationResult(
            profile=participant,
            inspection=replace(
                participant_inspection,
                root=profile_store_dir(participant),
            ),
            authority_profile=authority,
            authority_inspection=replace(
                authority_inspection,
                root=profile_store_dir(authority),
            ),
            active_profile_name=participant.name,
            scenario_id=scenario_id,
        )
    except Exception:
        if not committed:
            for destination, source in reversed(published):
                if destination.exists() and not source.exists():
                    os.replace(destination, source)
        raise
    finally:
        if batch.exists() and not batch.is_symlink():
            shutil.rmtree(batch)
