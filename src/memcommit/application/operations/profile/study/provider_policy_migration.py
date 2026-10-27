"""Explicit pilot migration of provider policy on registered Study groups."""

from __future__ import annotations

from dataclasses import dataclass, replace

from memcommit.application.operations.profile.config import (
    ProfileRegistry,
    load_profile_registry,
    study_run_identity,
)
from memcommit.models.profile import Profile
from memcommit.application.operations.profile.errors import ProfileError
from memcommit.application.operations.profile.model._storage import (
    _write_registry,
)
from .topology import group_study_run_profiles


@dataclass(frozen=True)
class StudyProviderPolicyMigrationResult:
    """One atomic pilot migration of registered Study Profiles."""

    generation: int
    migrated_study_count: int
    migrated_profile_count: int


def migrate_visible_study_provider_policy(
    *,
    target_version: str,
    target_digest: str,
    accepted_sources: frozenset[tuple[str | None, str | None]],
) -> StudyProviderPolicyMigrationResult:
    """Atomically repin the remaining registered members of each Study.

    Every group must share one explicitly accepted source condition before
    any registry replacement, including groups with only one member left.
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
    registry = load_profile_registry()
    migrated_uids: set[str] = set()
    migrated_studies = 0
    for group in group_study_run_profiles(registry.profiles):
        identity = study_run_identity(group.profiles[0])
        assert identity is not None
        current = (
            identity.provider_policy_version,
            identity.provider_policy_digest,
        )
        if current == target:
            continue
        if current not in accepted_sources:
            raise ProfileError(
                f"Visible Study {group.uid!r} has an unaccepted provider policy."
            )
        migrated_studies += 1
        migrated_uids.update(profile.uid for profile in group.profiles)

    if not migrated_uids:
        return StudyProviderPolicyMigrationResult(
            generation=registry.generation,
            migrated_study_count=0,
            migrated_profile_count=0,
        )

    profiles: list[Profile] = []
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
    )
    _write_registry(updated)
    return StudyProviderPolicyMigrationResult(
        generation=updated.generation,
        migrated_study_count=migrated_studies,
        migrated_profile_count=len(migrated_uids),
    )
