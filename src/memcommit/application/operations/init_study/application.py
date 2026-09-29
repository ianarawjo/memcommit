"""Initialize isolated Study runs from packaged scenarios."""

from __future__ import annotations

import re
import shutil
import uuid
from datetime import datetime, timezone

from memcommit.application.operations.init_study.model import StudyInitializationResult
from memcommit.application.operations.init_study.profile.composition import (
    _coffee_study_packages,
    _legacy_study_packages,
)
from memcommit.application.operations.init_study.profile.publication import (
    _publish_study_run_pair,
)
from memcommit.application.operations.profile.config import (
    AUTHORING_PROFILE_NAME,
    ProfileConfigError,
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_stores_dir,
    validate_profile_name,
)
from memcommit.application.operations.profile.model import (
    ProfileError,
    _registry_lock,
)


def init_legacy_study_profile(
    *,
    name: str | None = None,
    provider_policy_version: str,
    provider_policy_digest: str,
) -> StudyInitializationResult:
    """Create one isolated run directly from the packaged Legacy scenario."""

    from memcommit.study_scenarios.legacy import (
        LEGACY_BASELINE_UID,
        LEGACY_SCENARIO_ID,
    )

    generated_uid = uuid.uuid4()
    created = datetime.now(timezone.utc)
    if name is not None:
        try:
            name = validate_profile_name(name)
        except (ProfileConfigError, ValueError) as error:
            raise ProfileError("Study Profile name is invalid.") from error
    if name == AUTHORING_PROFILE_NAME:
        raise ProfileError("The fixed authoring name cannot identify a Study Profile.")

    with _registry_lock():
        registry = load_profile_registry()
        # Allocate automatic names inside the same lock that publishes the pair.
        profile_name = (
            name
            if name is not None
            else generate_study_profile_name(created=created, registry=registry)
        )
        staging = profile_stores_dir() / (
            f".{profile_name}.legacy-source-{uuid.uuid4().hex}"
        )
        staging.mkdir()
        try:
            packages, scenario_digest = _legacy_study_packages(staging)
            baseline = ProfileEntry(
                uid=LEGACY_BASELINE_UID,
                name=LEGACY_SCENARIO_ID,
                kind="MANAGED",
            )
            return _publish_study_run_pair(
                registry,
                baseline=baseline,
                packages=packages,
                study_name=profile_name,
                study_uid=str(generated_uid),
                created_at=created.isoformat(),
                baseline_digest=scenario_digest,
                provider_policy_version=provider_policy_version,
                provider_policy_digest=provider_policy_digest,
                scenario_id=LEGACY_SCENARIO_ID,
            )
        finally:
            if staging.exists() and not staging.is_symlink():
                shutil.rmtree(staging)


def init_coffee_study_profile(
    *,
    name: str | None = None,
    provider_policy_version: str,
    provider_policy_digest: str,
) -> StudyInitializationResult:
    """Create one isolated run from the built-in ``coffee`` scenario."""

    from memcommit.study_scenarios.coffee import (
        COFFEE_BASELINE_UID,
        COFFEE_DIGEST,
        COFFEE_SCENARIO_ID,
    )

    generated_uid = uuid.uuid4()
    created = datetime.now(timezone.utc)
    if name is not None:
        try:
            name = validate_profile_name(name)
        except (ProfileConfigError, ValueError) as error:
            raise ProfileError("Study Profile name is invalid.") from error
    if name == AUTHORING_PROFILE_NAME:
        raise ProfileError("The fixed authoring name cannot identify a Study Profile.")

    with _registry_lock():
        registry = load_profile_registry()
        # The editable console suggestion is an exact name; only unnamed
        # requests allocate a fresh sequence here, never silently retarget edits.
        profile_name = (
            name
            if name is not None
            else generate_study_profile_name(created=created, registry=registry)
        )
        staging = profile_stores_dir() / (
            f".{profile_name}.coffee-source-{uuid.uuid4().hex}"
        )
        staging.mkdir()
        try:
            packages = _coffee_study_packages(staging)
            # The built-in scenario behaves as an immutable virtual baseline:
            # its stable UID and content digest provide the same run provenance
            # without publishing a mutable Profile that could drift.
            baseline = ProfileEntry(
                uid=COFFEE_BASELINE_UID,
                name=COFFEE_SCENARIO_ID,
                kind="MANAGED",
            )
            return _publish_study_run_pair(
                registry,
                baseline=baseline,
                packages=packages,
                study_name=profile_name,
                study_uid=str(generated_uid),
                created_at=created.isoformat(),
                baseline_digest=COFFEE_DIGEST,
                provider_policy_version=provider_policy_version,
                provider_policy_digest=provider_policy_digest,
                scenario_id=COFFEE_SCENARIO_ID,
            )
        finally:
            if staging.exists() and not staging.is_symlink():
                shutil.rmtree(staging)


def generate_study_profile_name(
    *,
    created: datetime | None = None,
    registry: ProfileRegistry | None = None,
) -> str:
    """Suggest study-YYMMDD-N locally; publication must hold the registry lock."""
    timestamp = created or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise ValueError("Study name timestamps must be timezone-aware.")
    day = timestamp.astimezone().strftime("%y%m%d")
    registry = registry if registry is not None else load_profile_registry()
    pattern = re.compile(rf"study-{day}-([1-9][0-9]*)(?:-granted-memory)?", re.IGNORECASE)
    # Include tombstones and authority-only collisions: old study names must
    # not acquire a new meaning when a participant Profile is removed.
    used = (
        int(match.group(1))
        for profile in registry.profiles
        if (match := pattern.fullmatch(profile.name)) is not None
    )
    return f"study-{day}-{max(used, default=0) + 1}"
