"""Pure validation and selection of registered Study Profile groups."""

from __future__ import annotations

from dataclasses import replace

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
    """Group by durable Study identity, with one Profile per named session."""
    identities = {}
    members: dict[str, list[Profile]] = {}
    sessions: dict[str, set[str | None]] = {}
    names: dict[str, str] = {}
    for profile in profiles:
        identity = study_run_identity(profile)
        if identity is None:
            continue
        if (
            identity.name.casefold() in names
            and names[identity.name.casefold()] != identity.uid
        ):
            raise ProfileError("Study run names must be unique.")
        names[identity.name.casefold()] = identity.uid
        if identity.uid in identities and replace(identity, session=None) != replace(
            identities[identity.uid], session=None
        ):
            raise ProfileError("Study session provenance is inconsistent.")
        seen_sessions = sessions.setdefault(identity.uid, set())
        if identity.session in seen_sessions or (
            seen_sessions and (identity.session is None or None in seen_sessions)
        ):
            raise ProfileError("Study run Profile roles must be unique.")
        seen_sessions.add(identity.session)
        identities[identity.uid] = identity
        members.setdefault(identity.uid, []).append(profile)
    return tuple(
        StudyRunProfileGroup(
            uid, identities[uid].name, identities[uid].created_at, tuple(profiles)
        )
        for uid, profiles in members.items()
    )


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
