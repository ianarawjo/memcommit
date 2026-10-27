"""Frozen Profile inventory and Study membership projection."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.adapters.console.commands.profile._support import _fail
from memcommit.adapters.console.commands.profile.presentation import (
    _print_current_profile,
    _print_profile_inventory,
)
from memcommit.application.operations.profile.config import ProfileConfigError, study_run_identity
from memcommit.application.operations.profile.model._storage import ProfileError
from memcommit.application.operations.profile.model.lifecycle import list_profiles
from memcommit.application.operations.profile.study.topology import (
    group_study_run_profiles,
)


def _profile_rows() -> tuple[object, tuple[object, ...]]:
    try:
        return list_profiles()
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)


@dataclass(frozen=True)
class _ProfileStudyMembership:
    uid: str
    name: str
    created_at: str
    role: str
    first: bool
    last: bool
    profile_count: int
    session: str | None = None


def _study_memberships(registry) -> dict[str, _ProfileStudyMembership]:
    try:
        groups = group_study_run_profiles(registry.profiles)
    except (ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)
    profile_positions = {
        profile.uid: index for index, profile in enumerate(registry.profiles)
    }
    memberships: dict[str, _ProfileStudyMembership] = {}
    for group in groups:
        members = group.profiles
        positions = tuple(profile_positions[profile.uid] for profile in members)
        if positions != tuple(range(positions[0], positions[0] + len(members))):
            _fail(ProfileError("Study Profile entries must remain contiguous."))
        for profile in members:
            identity = study_run_identity(profile)
            assert identity is not None
            if profile.uid in memberships:
                _fail(ProfileError("Profile has conflicting Study provenance."))
            memberships[profile.uid] = _ProfileStudyMembership(
                uid=group.uid,
                name=group.name,
                created_at=group.created_at,
                role=identity.role,
                first=profile.uid == members[0].uid,
                last=profile.uid == members[-1].uid,
                profile_count=len(members),
                session=identity.session,
            )
    return memberships


def list_cmd() -> None:
    """List locally registered whole-store profiles."""

    registry, inspections = _profile_rows()
    memberships = _study_memberships(registry)
    _print_profile_inventory(registry, inspections, memberships)


def current_cmd() -> None:
    """Show the selected profile and its current Context."""

    registry, inspections = _profile_rows()
    _print_current_profile(registry, inspections)
