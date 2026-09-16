"""Explicit pilot migration of provider policy on visible Study pairs."""

from __future__ import annotations

from dataclasses import dataclass, replace

from memcommit.application.operations.profile.config import (
    ProfileEntry,
    ProfileRegistry,
    StudyRunIdentity,
    load_profile_registry,
    study_run_identity,
)
from memcommit.application.operations.profile.errors import ProfileError
from memcommit.application.operations.profile.model._storage import (
    _registry_lock,
    _write_registry,
)


@dataclass(frozen=True)
class StudyProviderPolicyMigrationResult:
    """One atomic pilot migration of visible current Study pairs."""

    generation: int
    migrated_study_count: int
    migrated_profile_count: int


def migrate_visible_study_provider_policy(
    *,
    target_version: str,
    target_digest: str,
    accepted_sources: frozenset[tuple[str | None, str | None]],
) -> StudyProviderPolicyMigrationResult:
    """Atomically repin every visible current Study pair during the pilot.

    Removed Profile tombstones retain their historical provenance. Every
    visible participant/authority pair must be complete and must share one
    explicitly accepted source condition before any registry replacement.
    """

    if not target_version or len(target_version) > 128:
        raise ProfileError("Study provider policy version is invalid.")
    if (
        not isinstance(target_digest, str)
        or len(target_digest) != 64
        or any(character not in "0123456789abcdef" for character in target_digest)
    ):
        raise ProfileError("Study provider policy digest is invalid.")
    if not accepted_sources:
        raise ProfileError("Study provider migration has no accepted source.")

    target = (target_version, target_digest)
    with _registry_lock():
        registry = load_profile_registry()
        removed = frozenset(registry.removed_profile_uids)
        groups: dict[str, list[tuple[ProfileEntry, StudyRunIdentity]]] = {}
        for profile in registry.profiles:
            if profile.uid in removed:
                continue
            identity = study_run_identity(profile)
            if identity is None:
                continue
            groups.setdefault(identity.uid, []).append((profile, identity))

        migrated_uids: set[str] = set()
        migrated_studies = 0
        for study_uid, members in groups.items():
            roles = {identity.role for _profile, identity in members}
            conditions = {
                (
                    identity.provider_policy_version,
                    identity.provider_policy_digest,
                )
                for _profile, identity in members
            }
            if len(members) != 2 or roles != {"PARTICIPANT", "GRANTED_MEMORY"}:
                raise ProfileError(
                    f"Visible Study {study_uid!r} does not contain one complete pair."
                )
            if len(conditions) != 1:
                raise ProfileError(
                    f"Visible Study {study_uid!r} has inconsistent provider policy."
                )
            current = next(iter(conditions))
            if current == target:
                continue
            if current not in accepted_sources:
                raise ProfileError(
                    f"Visible Study {study_uid!r} has an unaccepted provider policy."
                )
            migrated_studies += 1
            migrated_uids.update(profile.uid for profile, _identity in members)

        if not migrated_uids:
            return StudyProviderPolicyMigrationResult(
                generation=registry.generation,
                migrated_study_count=0,
                migrated_profile_count=0,
            )

        profiles: list[ProfileEntry] = []
        for profile in registry.profiles:
            if profile.uid not in migrated_uids:
                profiles.append(profile)
                continue
            assert profile.source is not None
            source = dict(profile.source)
            source["provider_policy_version"] = target_version
            source["provider_policy_digest"] = target_digest
            profiles.append(replace(profile, source=source))

        updated = ProfileRegistry(
            generation=max(1, registry.generation + 1),
            active_uid=registry.active_uid,
            profiles=tuple(profiles),
            grants=registry.grants,
            removed_profile_uids=registry.removed_profile_uids,
            grant_placements=registry.grant_placements,
        )
        _write_registry(updated)
        return StudyProviderPolicyMigrationResult(
            generation=updated.generation,
            migrated_study_count=migrated_studies,
            migrated_profile_count=len(migrated_uids),
        )
