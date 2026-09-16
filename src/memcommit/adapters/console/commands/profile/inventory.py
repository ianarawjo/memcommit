"""Frozen Profile inventory and Study membership projection."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.adapters.console.commands.profile._support import _fail
from memcommit.adapters.console.commands.profile.presentation import (
    _print_current_profile,
    _print_profile_inventory,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model._storage import ProfileError
from memcommit.application.operations.profile.model.lifecycle import list_profiles
from memcommit.application.operations.profile.study.topology import (
    study_run_profile_pairs,
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
    removed_count: int


def _study_memberships(registry) -> dict[str, _ProfileStudyMembership]:
    try:
        pairs = study_run_profile_pairs(registry.profiles)
    except (ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)
    study_names = [
        pair.name.casefold() for pair in pairs
    ]
    if len(study_names) != len(set(study_names)):
        _fail(ProfileError("Study display names must be unique."))
    profile_positions = {
        profile.uid: index for index, profile in enumerate(registry.profiles)
    }
    memberships: dict[str, _ProfileStudyMembership] = {}
    for pair in pairs:
        if (
            profile_positions[pair.authority.uid]
            != profile_positions[pair.participant.uid] + 1
        ):
            _fail(ProfileError("Study run Profile pair must remain contiguous."))
        pair_members = (
            (pair.participant, "PARTICIPANT"),
            (pair.authority, "GRANTED_MEMORY"),
        )
        visible_members = tuple(
            profile
            for profile, _role in pair_members
            if not registry.is_removed(profile)
        )
        for profile, role in pair_members:
            if profile.uid in memberships:
                _fail(ProfileError("Profile has conflicting Study provenance."))
            memberships[profile.uid] = _ProfileStudyMembership(
                uid=pair.uid,
                name=pair.name,
                created_at=pair.created_at,
                role=role,
                first=bool(visible_members and profile.uid == visible_members[0].uid),
                last=bool(visible_members and profile.uid == visible_members[-1].uid),
                profile_count=len(pair_members),
                removed_count=len(pair_members) - len(visible_members),
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
