"""Pure validation and selection of registered Study Profile groups."""

from __future__ import annotations

from memcommit.application.operations.profile.config import (
    ProfileRegistry,
    study_run_identity,
    validate_profile_name,
)
from memcommit.models.profile import Profile
from memcommit.application.operations.profile.errors import ProfileError

from .model import StudyRunProfileGroup


def group_study_run_profiles(
    profiles: tuple[Profile, ...],
) -> tuple[StudyRunProfileGroup, ...]:
    """Group each current Study label with its one registered local Profile."""
    result = []
    seen_uids: set[str] = set()
    seen_names: set[str] = set()
    for profile in profiles:
        identity = study_run_identity(profile)
        if identity is None:
            continue
        if identity.uid in seen_uids:
            raise ProfileError("Study run Profile roles must be unique.")
        if identity.name.casefold() in seen_names:
            raise ProfileError("Study run names must be unique.")
        seen_uids.add(identity.uid)
        seen_names.add(identity.name.casefold())
        result.append(
            StudyRunProfileGroup(
                identity.uid, identity.name, identity.created_at, profile
            )
        )
    return tuple(result)


def _study_target(
    registry: ProfileRegistry,
    name: str,
) -> tuple[str, str, tuple[Profile, ...]]:
    """Resolve one current Study to its stable member identities."""

    canonical = validate_profile_name(name)
    matches: list[tuple[str, str, tuple[Profile, ...]]] = []
    matches.extend(
        (
            group.uid,
            group.name,
            group.profiles,
        )
        for group in group_study_run_profiles(registry.profiles)
        if group.name.casefold() == canonical.casefold()
    )
    if not matches:
        raise ProfileError(f"Study {canonical!r} does not exist.")
    if len(matches) != 1:
        raise ProfileError(f"Study selector {canonical!r} is ambiguous.")
    return matches[0]
