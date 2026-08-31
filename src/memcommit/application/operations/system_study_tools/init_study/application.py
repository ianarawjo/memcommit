"""Initialize isolated Study runs from packaged scenarios."""

from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timezone

from memcommit.application.operations.system_study_tools.init_study.model import StudyInitializationResult
from memcommit.application.operations.system_study_tools.init_study.profile.composition import (
    _coffee_study_packages,
    _legacy_study_packages,
)
from memcommit.application.operations.system_study_tools.init_study.profile.publication import (
    _publish_study_run_pair,
)
from memcommit.application.operations.profiles.profile.config import (
    AUTHORING_PROFILE_NAME,
    ProfileConfigError,
    ProfileEntry,
    load_profile_registry,
    profile_stores_dir,
    validate_profile_name,
)
from memcommit.application.operations.profiles.profile.model import (
    ProfileError,
    _registry_lock,
    study_profile_groups,
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
    generated_uid: uuid.UUID | None = None,
) -> str:
    """Return the editable timestamp-and-UUID default for one Study run."""
    timestamp = created or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise ValueError("Study name timestamps must be timezone-aware.")
    timestamp = timestamp.astimezone(timezone.utc)
    suffix = generated_uid or uuid.uuid4()
    return f"study-{timestamp.strftime('%Y%m%dT%H%M%SZ')}-{str(suffix)[:8]}"
