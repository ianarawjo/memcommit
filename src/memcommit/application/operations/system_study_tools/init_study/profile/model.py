"""Internal data contracts for init-study Profile construction."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from memcommit.application.operations.profiles.profile.config import (
    ProfileConfigError,
    ProfileEntry,
    validate_profile_name,
)
from memcommit.application.operations.profiles.profile.model._storage import (
    ProfileError,
    StoreInspection,
)

_STUDY_BUNDLE_NAMESPACE = uuid.UUID("50b72d54-cfbe-4f89-8f7f-1e6c785d8552")


@dataclass(frozen=True)
class StudyImportResult:
    profiles: tuple[ProfileEntry, ...]
    inspections: tuple[StoreInspection, ...]


@dataclass(frozen=True)
class _StudyProfileSource:
    """One validated profile store declared by a study task package."""

    task: int
    name: str
    role: str
    store: Path
    entries: tuple[object, ...]
    inspection: StoreInspection


@dataclass(frozen=True)
class _StudyTaskPackage:
    """Manifest data that is still independent of local Profile UIDs."""

    task: int
    schema_version: int
    manifest: dict[str, object]
    manifest_digest: str
    profiles: tuple[_StudyProfileSource, ...]
    grant_templates: tuple[dict[str, object], ...]
    query_view_count: int


def _study_run_authority_profile_name(study_name: str) -> str:
    """Return the visible run-private authority Profile name."""

    try:
        return validate_profile_name(f"{study_name}-granted-memory")
    except (ProfileConfigError, ValueError) as error:
        raise ProfileError(
            "Study name is too long to create its granted-memory Profile."
        ) from error
