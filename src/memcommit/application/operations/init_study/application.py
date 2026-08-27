"""Initialize isolated Study runs from versioned or editable inputs."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import shutil
from typing import Callable
import uuid

from memcommit.application.operations.init_study.composition import (
    _coffee_study_packages,
    _snapshot_study_baseline,
)
from memcommit.application.operations.init_study.model import StudyInitializationResult
from memcommit.application.operations.init_study.publication import _publish_study_run_pair
from memcommit.application.operations.profile.config import (
    AUTHORING_PROFILE_NAME,
    ProfileConfigError,
    ProfileEntry,
    load_profile_registry,
    profile_store_dir,
    profile_stores_dir,
    validate_profile_name,
)
from memcommit.application.operations.profile.model import (
    ProfileError,
    STUDY_BASELINE_PROFILE_NAME,
    _registry_lock,
    _study_baseline_tasks,
    baseline_store_digest,
    study_profile_groups,
)


def init_study_profile(
    baseline_profile_name: str = STUDY_BASELINE_PROFILE_NAME,
    *,
    name: str | None = None,
    provider_policy_version: str,
    provider_policy_digest: str,
    prewarm_workers: int = 96,
    prewarm_reasoning: str = "xhigh",
    prewarm_progress: Callable[[str], None] | None = None,
) -> StudyInitializationResult:
    """Create one isolated participant Profile and one authority Profile."""

    try:
        baseline_name = validate_profile_name(baseline_profile_name)
    except (ProfileConfigError, ValueError) as error:
        raise ProfileError("Study baseline Profile name is invalid.") from error

    generated_uid = uuid.uuid4()
    created = datetime.now(timezone.utc)
    if name is None:
        profile_name = generate_study_profile_name(
            created=created,
            generated_uid=generated_uid,
        )
    else:
        try:
            profile_name = validate_profile_name(name)
        except (ProfileConfigError, ValueError) as error:
            raise ProfileError("Study Profile name is invalid.") from error
    if profile_name == AUTHORING_PROFILE_NAME:
        raise ProfileError("The fixed authoring name cannot identify a Study Profile.")

    with _registry_lock():
        registry = load_profile_registry()
        baseline = registry.by_name(baseline_name)
        if baseline is None:
            bootstrap = (
                "; bootstrap it with 'mem profile import-study'"
                if baseline_name == STUDY_BASELINE_PROFILE_NAME
                else ""
            )
            raise ProfileError(
                f"Study baseline Profile {baseline_name!r} does not exist{bootstrap}."
            )
        if any(
            group.name.casefold() == profile_name.casefold()
            for group in study_profile_groups(registry.profiles)
        ):
            raise ProfileError(
                f"Profile name {profile_name!r} conflicts with an existing legacy "
                "Study group."
            )
        if any(
            baseline.uid in {grant.authority_profile_uid, grant.grantee_profile_uid}
            for grant in registry.grants
        ):
            # Grants are registry relationships, not owned baseline content.
            # Holding the same lock through publication makes the self-contained
            # source check part of the exact registry generation being copied.
            raise ProfileError(
                f"Study baseline Profile {baseline.name!r} participates in registry "
                "grants and cannot be copied as one self-contained Profile."
            )

        task_records = _study_baseline_tasks(baseline)
        source_root = profile_store_dir(baseline)
        before = baseline_store_digest(source_root)
        staging = profile_stores_dir() / (
            f".{profile_name}.study-source-{uuid.uuid4().hex}"
        )
        try:
            packages = _snapshot_study_baseline(baseline, task_records, staging)
            after = baseline_store_digest(source_root)
            if before != after:
                raise ProfileError("Study baseline changed during initialization.")
            initialization = _publish_study_run_pair(
                registry,
                baseline=baseline,
                packages=packages,
                study_name=profile_name,
                study_uid=str(generated_uid),
                created_at=created.isoformat(),
                baseline_digest=before,
                provider_policy_version=provider_policy_version,
                provider_policy_digest=provider_policy_digest,
                prewarm_workers=prewarm_workers,
                prewarm_reasoning=prewarm_reasoning,
                prewarm_progress=prewarm_progress,
                scenario_id="legacy-v1",
            )
        finally:
            if staging.exists() and not staging.is_symlink():
                shutil.rmtree(staging)

    # Registry entries are advertised as available, not installed.  First use
    # validates and materializes exactly one requested artifact in the active
    # participant overlay.
    from collections import Counter
    from memcommit.study_prewarm.registry import load_registry as load_prewarm_registry

    available = load_prewarm_registry(profile_store_dir(initialization.profile))
    counts = Counter(
        entry.operation
        for entry in (available.entries if available is not None else ())
        if entry.enabled
    )
    return replace(
        initialization,
        declared_compare_prewarms=counts["COMPARE"],
        declared_atomize_prewarms=counts["ATOMIZE"],
        declared_summarize_prewarms=counts["SUMMARIZE"],
        declared_update_prewarms=counts["UPDATE"],
        declared_sever_prewarms=counts["SEVER"],
        declared_directional_meld_prewarms=counts["MELD_DIRECTIONAL"],
        declared_meld_resolution_prewarms=counts["MELD_RESOLUTION"],
    )


def init_coffee_study_profile(
    *,
    name: str | None = None,
    provider_policy_version: str,
    provider_policy_digest: str,
) -> StudyInitializationResult:
    """Create one isolated run from the built-in ``coffee-v1`` scenario."""

    from memcommit.study_scenarios.coffee_v1 import (
        COFFEE_V1_BASELINE_UID,
        COFFEE_V1_DIGEST,
        COFFEE_V1_SCENARIO_ID,
    )

    generated_uid = uuid.uuid4()
    created = datetime.now(timezone.utc)
    if name is None:
        profile_name = generate_study_profile_name(
            created=created,
            generated_uid=generated_uid,
        )
    else:
        try:
            profile_name = validate_profile_name(name)
        except (ProfileConfigError, ValueError) as error:
            raise ProfileError("Study Profile name is invalid.") from error
    if profile_name == AUTHORING_PROFILE_NAME:
        raise ProfileError("The fixed authoring name cannot identify a Study Profile.")

    with _registry_lock():
        registry = load_profile_registry()
        if any(
            group.name.casefold() == profile_name.casefold()
            for group in study_profile_groups(registry.profiles)
        ):
            raise ProfileError(
                f"Profile name {profile_name!r} conflicts with an existing legacy "
                "Study group."
            )
        staging = profile_stores_dir() / (
            f".{profile_name}.coffee-v1-source-{uuid.uuid4().hex}"
        )
        staging.mkdir()
        try:
            packages = _coffee_study_packages(staging)
            # The built-in scenario behaves as an immutable virtual baseline:
            # its stable UID and content digest provide the same run provenance
            # without publishing a mutable Profile that could drift.
            baseline = ProfileEntry(
                uid=COFFEE_V1_BASELINE_UID,
                name=COFFEE_V1_SCENARIO_ID,
                kind="MANAGED",
            )
            return _publish_study_run_pair(
                registry,
                baseline=baseline,
                packages=packages,
                study_name=profile_name,
                study_uid=str(generated_uid),
                created_at=created.isoformat(),
                baseline_digest=COFFEE_V1_DIGEST,
                provider_policy_version=provider_policy_version,
                provider_policy_digest=provider_policy_digest,
                prewarm_workers=1,
                prewarm_reasoning="none",
                prewarm_progress=None,
                scenario_id=COFFEE_V1_SCENARIO_ID,
                prepare_prewarms=False,
            )
        finally:
            if staging.exists() and not staging.is_symlink():
                shutil.rmtree(staging)


def generate_study_profile_name(
    *,
    created: datetime | None = None,
    generated_uid: uuid.UUID | None = None,
) -> str:
    """Return the editable timestamp-and-UUID default for one Study run."""
    timestamp = created or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise ValueError("Study name timestamps must be timezone-aware.")
    timestamp = timestamp.astimezone(timezone.utc)
    suffix = generated_uid or uuid.uuid4()
    return f"study-{timestamp.strftime('%Y%m%dT%H%M%SZ')}-{str(suffix)[:8]}"
