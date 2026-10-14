"""Pure validation and selection of registered Study Profile groups."""

from __future__ import annotations

from memcommit.application.operations.profile.config import (
    ProfileEntry,
    ProfileRegistry,
    StudyRunIdentity,
    study_run_identity,
    validate_profile_name,
)
from memcommit.application.operations.profile.errors import ProfileError

from .model import StudyRunProfileGroup


def group_study_run_profiles(
    profiles: tuple[ProfileEntry, ...],
) -> tuple[StudyRunProfileGroup, ...]:
    """Group one or both remaining Study Profiles by their shared provenance."""

    grouped: dict[str, list[tuple[ProfileEntry, StudyRunIdentity]]] = {}
    order: list[str] = []
    for profile in profiles:
        identity = study_run_identity(profile)
        if identity is None:
            continue
        if identity.uid not in grouped:
            grouped[identity.uid] = []
            order.append(identity.uid)
        grouped[identity.uid].append((profile, identity))

    result: list[StudyRunProfileGroup] = []
    seen_names: set[str] = set()
    for study_uid in order:
        members = grouped[study_uid]
        roles = {identity.role for _profile, identity in members}
        # Deletion unregisters one member rather than retaining a placeholder.
        # A remaining member still owns the Study identity and display label.
        if not 1 <= len(members) <= 2 or len(roles) != len(members):
            raise ProfileError("Study run Profile roles must be unique.")
        identities = [identity for _profile, identity in members]
        shared = {
            (
                identity.name,
                identity.created_at,
                identity.baseline_profile_uid,
                identity.baseline_profile_name,
                identity.baseline_sha256,
                identity.provider_policy_version,
                identity.provider_policy_digest,
            )
            for identity in identities
        }
        if len(shared) != 1:
            raise ProfileError("Study run Profile provenance is inconsistent.")
        (
            name,
            created_at,
            _baseline_uid,
            _baseline_name,
            _digest,
            _provider_policy_version,
            _provider_policy_digest,
        ) = next(iter(shared))
        if name.casefold() in seen_names:
            raise ProfileError("Study run names must be unique.")
        seen_names.add(name.casefold())
        participant = next(
            (
                profile
                for profile, identity in members
                if identity.role == "PARTICIPANT"
            ),
            None,
        )
        authority = next(
            (
                profile
                for profile, identity in members
                if identity.role == "GRANTED_MEMORY"
            ),
            None,
        )
        result.append(
            StudyRunProfileGroup(
                uid=study_uid,
                name=name,
                created_at=created_at,
                participant=participant,
                authority=authority,
            )
        )
    return tuple(result)


def _study_target(
    registry: ProfileRegistry,
    name: str,
) -> tuple[str, str, tuple[ProfileEntry, ...]]:
    """Resolve one current Study to its stable member identities."""

    canonical = validate_profile_name(name)
    matches: list[tuple[str, str, tuple[ProfileEntry, ...]]] = []
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
