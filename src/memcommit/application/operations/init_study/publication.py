"""Copy discovered Study projects, then register and verify the complete run."""

from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import uuid

from memcommit.application.operations.init_study.model import StudyInitializationResult
from memcommit.application.operations.profile.config import (
    STUDY_RUN_PARTICIPANT_SOURCE_KIND,
    ProfileConfigError,
    ProfileRegistry,
    load_profile_registry,
    profile_store_dir,
    validate_profile_name,
)
from memcommit.application.operations.profile.model._storage import (
    ProfileError,
    _write_registry,
)
from memcommit.application.operations.profile.project_root import (
    validate_profile_root,
    write_profile_marker,
)
from memcommit.configuration.config import Config
from memcommit.models.profile import Profile
from memcommit.persistence.command_ledger.study_records import (
    initialize_study_records,
)
from .project_templates import copy_study_project


def publish_local_study_profile(
    registry: ProfileRegistry,
    *,
    project_roots: tuple[Path, ...],
    study_name: str,
    study_uid: str,
    created_at: str,
    provider_policy_version: str,
    provider_policy_digest: str,
) -> StudyInitializationResult:
    """Stage a run once, then save and read back its Profile registration."""
    from memcommit.application.operations.profile.study.topology import (
        group_study_run_profiles,
    )

    if any(
        group.name.casefold() == study_name.casefold()
        for group in group_study_run_profiles(registry.profiles)
    ):
        raise ProfileError(f"Study {study_name!r} already exists.")
    study_parent = Path(Config().get("study_root_dir")).resolve()
    run_root = study_parent / study_name
    records_root = run_root / "study-records"
    profiles = _build_study_profiles(
        project_roots,
        run_root=run_root,
        study_name=study_name,
        study_uid=study_uid,
        created_at=created_at,
        provider_policy_version=provider_policy_version,
        provider_policy_digest=provider_policy_digest,
    )
    occupied_names = {profile.name.casefold() for profile in registry.profiles}
    if study_name.casefold() in occupied_names or any(
        profile.name.casefold() in occupied_names for profile in profiles
    ):
        raise ProfileError("Study or session Profile name already exists.")
    if run_root.exists() or run_root.is_symlink():
        # Retained project documents and research records cannot be adopted by a new run.
        raise ProfileError(f"Study folder is already occupied: {run_root}")
    for profile in profiles:
        validate_profile_root(profile, profile.root_dir, registry)
    updated = ProfileRegistry(
        generation=max(1, registry.generation + 1),
        active_uid=profiles[0].uid,
        profiles=(*registry.profiles, *profiles),
    )
    study_parent.mkdir(parents=True, exist_ok=True)
    inspections = []
    with TemporaryDirectory(prefix=f".{study_name}.study-run-", dir=study_parent) as staging:
        batch = Path(staging)
        for project_root, profile in zip(project_roots, profiles, strict=True):
            project_staging = batch / project_root.name
            staged_store_root = project_staging / ".mem"
            inspection = copy_study_project(
                project_root,
                project_staging,
                published_root=Path(profile.root_dir),
                created_at=created_at,
            )
            write_profile_marker(store_root=staged_store_root, uid=profile.uid)
            inspections.append(replace(inspection, root=profile_store_dir(profile)))
        initialize_study_records(
            batch / "study-records",
            study_uid=study_uid,
            study_name=study_name,
            created_at=created_at,
            profiles_by_session={
                project_root.name: profile
                for project_root, profile in zip(project_roots, profiles, strict=True)
            },
        )
        # Publish only complete copies; TemporaryDirectory removes failed staging.
        os.replace(batch, run_root)
    try:
        _write_registry(updated)
        if load_profile_registry() != updated:
            raise ProfileError("Saved Study registration does not match the prepared run.")
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        # A failed write may already have replaced the registry. Keep its projects.
        raise ProfileError(
            f"Study registration could not be confirmed. Prepared projects and records "
            f"were retained at {run_root}: {error}"
        ) from error
    return StudyInitializationResult(
        profile=profiles[0],
        inspection=inspections[0],
        active_profile_name=profiles[0].name,
        study_name=study_name,
        profiles=profiles,
        inspections=tuple(inspections),
        records_root=str(records_root),
    )


def _build_study_profiles(
    project_roots: tuple[Path, ...],
    *,
    run_root: Path,
    study_name: str,
    study_uid: str,
    created_at: str,
    provider_policy_version: str,
    provider_policy_digest: str,
) -> tuple[Profile, ...]:
    common_source = {
        "kind": STUDY_RUN_PARTICIPANT_SOURCE_KIND,
        "study_uid": study_uid,
        "study_name": study_name,
        "created_at": created_at,
        "provider_policy_version": provider_policy_version,
        "provider_policy_digest": provider_policy_digest,
        "study_records_root": str(run_root / "study-records"),
    }
    try:
        return tuple(
            Profile(
                uid=str(uuid.uuid4()),
                name=validate_profile_name(f"{study_name}-{project_root.name}"),
                kind="MANAGED",
                source={**common_source, "study_session": project_root.name},
                root_dir=str(run_root / project_root.name),
            )
            for project_root in project_roots
        )
    except ProfileConfigError as error:
        raise ProfileError(
            "Study name is too long for its session Profile names."
        ) from error
