"""Initialize isolated Study runs by copying the prepared projects."""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from datetime import datetime, timezone

from memcommit.application.operations.init_study.model import StudyInitializationResult
from memcommit.application.operations.init_study.project_templates import (
    list_study_project_roots,
)
from memcommit.application.operations.init_study.publication import (
    publish_local_study_profile,
)
from memcommit.application.operations.profile.config import (
    AUTHORING_PROFILE_NAME,
    ProfileConfigError,
    ProfileRegistry,
    load_profile_registry,
    validate_profile_name,
)
from memcommit.application.operations.profile.errors import ProfileError


def initialize_study(
    *,
    name: str | None = None,
    provider_policy_version: str,
    provider_policy_digest: str,
) -> StudyInitializationResult:
    """Create one isolated Study by copying its prepared project folders."""

    generated_uid = uuid.uuid4()
    created = datetime.now(timezone.utc)
    if name is not None:
        try:
            name = validate_profile_name(name)
        except (ProfileConfigError, ValueError) as error:
            raise ProfileError("Study Profile name is invalid.") from error
    if name == AUTHORING_PROFILE_NAME:
        raise ProfileError("The fixed authoring name cannot identify a Study Profile.")

    registry = load_profile_registry()
    # The editable console suggestion is an exact name; only unnamed
    # requests allocate a fresh sequence here, never silently retarget edits.
    profile_name = (
        name
        if name is not None
        else generate_study_profile_name(created=created, registry=registry)
    )
    project_roots = list_study_project_roots()
    return publish_local_study_profile(
        registry,
        project_roots=project_roots,
        study_name=profile_name,
        study_uid=str(generated_uid),
        created_at=created.isoformat(),
        provider_policy_version=provider_policy_version,
        provider_policy_digest=provider_policy_digest,
    )


def generate_study_profile_name(
    *,
    created: datetime | None = None,
    registry: ProfileRegistry | None = None,
) -> str:
    """Suggest study-YYMMDD-N for sequential use of the local registry."""
    timestamp = created or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise ValueError("Study name timestamps must be timezone-aware.")
    day = timestamp.astimezone().strftime("%y%m%d")
    registry = registry if registry is not None else load_profile_registry()
    pattern = re.compile(rf"study-{day}-([1-9][0-9]*)", re.IGNORECASE)
    from memcommit.configuration.config import Config

    parent = Path(Config().get("study_root_dir"))
    # Retained records reserve the physical folder even after unregistration.
    occupied = [profile.name for profile in registry.profiles]
    # Study provenance supplies the run name independently of session suffixes.
    occupied.extend(
        profile.source["study_name"]
        for profile in registry.profiles
        if profile.source and profile.source.get("kind") == "STUDY_RUN"
    )
    if parent.is_dir():
        occupied.extend(path.name for path in parent.iterdir())
    used = (
        int(match.group(1))
        for name in occupied
        if (match := pattern.fullmatch(name)) is not None
    )
    return f"study-{day}-{max(used, default=0) + 1}"
