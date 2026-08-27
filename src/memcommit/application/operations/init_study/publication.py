"""Atomically publish one init-study participant/authority Profile pair."""

from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import shutil
import uuid

from memcommit.application.operations.init_study.composition import (
    _compose_study_run_pair,
)
from memcommit.application.operations.init_study.model import StudyInitializationResult
from memcommit.application.operations.profile.config import (
    ProfileConfigError,
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_store_dir,
    profile_stores_dir,
)
from memcommit.application.operations.profile.model import (
    ProfileError,
    _STUDY_RUN_GRANTED_SOURCE_KIND,
    _STUDY_RUN_SOURCE_KIND,
    _StudyTaskPackage,
    _inspection_with_grants,
    _materialize_study_grants,
    _study_run_authority_profile_name,
    _write_registry,
    inspect_store,
)


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
        grants = _materialize_study_grants(
            merged,
            profiles_by_name,
            roots_by_name,
        )
        namespace = uuid.UUID(study_uid)
        grants = tuple(
            replace(grant, uid=str(uuid.uuid5(namespace, grant.uid)))
            for grant in grants
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
