"""Pure validation and selection of current participant/authority pairs."""

from __future__ import annotations

from memcommit.application.operations.profile.config import (
    ProfileEntry,
    ProfileRegistry,
    StudyRunIdentity,
    study_run_identity,
    validate_profile_name,
)
from memcommit.application.operations.profile.errors import ProfileError

from .model import StudyRunProfilePair


def study_run_profile_pairs(
    profiles: tuple[ProfileEntry, ...],
) -> tuple[StudyRunProfilePair, ...]:
    """Validate and group current two-Profile Study runs by provenance."""

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

    result: list[StudyRunProfilePair] = []
    seen_names: set[str] = set()
    for study_uid in order:
        members = grouped[study_uid]
        roles = {identity.role for _profile, identity in members}
        if len(members) != 2 or roles != {"PARTICIPANT", "GRANTED_MEMORY"}:
            raise ProfileError("Study run Profile pair is incomplete.")
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
            profile for profile, identity in members if identity.role == "PARTICIPANT"
        )
        authority = next(
            profile
            for profile, identity in members
            if identity.role == "GRANTED_MEMORY"
        )
        result.append(
            StudyRunProfilePair(
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
            pair.uid,
            pair.name,
            (pair.participant, pair.authority),
        )
        for pair in study_run_profile_pairs(registry.profiles)
        if pair.name.casefold() == canonical.casefold()
    )
    if not matches:
        raise ProfileError(f"Study {canonical!r} does not exist.")
    if len(matches) != 1:
        raise ProfileError(f"Study selector {canonical!r} is ambiguous.")
    return matches[0]
