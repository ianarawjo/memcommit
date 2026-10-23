"""Publish one complete local Study Profile in one registry generation."""

from __future__ import annotations

import os
import shutil
import uuid
from dataclasses import replace
from pathlib import Path

from memcommit.application.operations.init_study.model import StudyInitializationResult
from memcommit.application.operations.profile.config import (
    STUDY_RUN_PARTICIPANT_SOURCE_KIND,
    ProfileConfigError,
    ProfileRegistry,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.application.operations.profile.model._storage import (
    ProfileError,
    _write_registry,
)
from memcommit.models.profile import Profile
from .composition import compose_local_study_store
from .model import StudyTaskData

_STUDY_RUN_SOURCE_KIND = STUDY_RUN_PARTICIPANT_SOURCE_KIND


def publish_local_study_profile(
    registry: ProfileRegistry,
    *,
    baseline: Profile,
    packages: dict[int, StudyTaskData],
    study_name: str,
    study_uid: str,
    created_at: str,
    baseline_digest: str,
    provider_policy_version: str,
    provider_policy_digest: str,
    scenario_id: str = "legacy",
) -> StudyInitializationResult:
    """Publish the complete local run as one registry transaction."""

    if registry.by_name(study_name) is not None:
        raise ProfileError(f"Profile {study_name!r} already exists.")

    from memcommit.application.operations.profile.study.topology import (
        group_study_run_profiles,
    )

    if any(
        group.name.casefold() == study_name.casefold()
        for group in group_study_run_profiles(registry.profiles)
    ):
        # A remaining member still owns the Study label, even after its Profile
        # was independently renamed. Only deleting the final member frees it.
        raise ProfileError(f"Study {study_name!r} already exists.")

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
    from memcommit.configuration.config import Config

    study_parent = Path(Config().get("study_root_dir"))
    run_root = study_parent / study_uid
    study_parent.mkdir(parents=True, exist_ok=True)
    if run_root.exists() or run_root.is_symlink():
        raise ProfileError("Study run directory is already occupied.")
    participant = Profile(
        uid=str(uuid.uuid4()),
        name=study_name,
        kind="MANAGED",
        source={"kind": _STUDY_RUN_SOURCE_KIND, **common_source},
        root_dir=str((run_root / "participant").resolve()),
    )
    batch = study_parent / f".{study_name}.study-run-{uuid.uuid4().hex}"
    batch.mkdir()
    participant_staging = batch / participant.uid
    published: list[tuple[Path, Path]] = []
    committed = False
    try:
        participant_inspection = compose_local_study_store(
            packages, participant_staging
        )
        updated = ProfileRegistry(
            generation=max(1, registry.generation + 1),
            # Selection and the complete local run become visible together.
            active_uid=participant.uid,
            profiles=(*registry.profiles, participant),
        )

        for profile, source in ((participant, participant_staging),):
            destination = profile_store_dir(profile)
            if destination.exists() or destination.is_symlink():
                raise ProfileError("Managed profile destination is occupied.")
            from memcommit.application.operations.profile.project_root import (
                prepare_profile_root,
                write_profile_marker,
            )

            prepare_profile_root(
                profile=profile,
                requested_root=profile.root_dir,
                registry=registry,
            )
            write_profile_marker(store_root=source, uid=profile.uid)
            os.replace(source, destination)
            published.append((destination, source))
        try:
            _write_registry(updated)
        except Exception as error:
            try:
                replacement_is_visible = load_profile_registry() == updated
            except (OSError, ProfileConfigError, ValueError) as read_error:
                # An unreadable registry cannot authorize deleting a possibly
                # published Study pair. Preserve both Stores for inspection.
                committed = True
                raise ProfileError(
                    "Study registry publication could not be confirmed; inspect the registered Profiles."
                ) from read_error
            if replacement_is_visible:
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
        if not committed:
            # Only empty directories created for this new run may be removed.
            for directory in (run_root / "participant", run_root):
                try:
                    directory.rmdir()
                except OSError:
                    pass
