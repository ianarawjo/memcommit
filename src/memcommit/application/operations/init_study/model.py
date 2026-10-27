"""Typed results published by the init-study application."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from memcommit.models.profile import Profile

if TYPE_CHECKING:
    from memcommit.application.operations.profile.model import StoreInspection


@dataclass(frozen=True)
class StudyInitializationResult:
    """Discovered ready projects with the first sorted project selected."""

    profile: Profile
    inspection: StoreInspection
    active_profile_name: str
    study_name: str
    profiles: tuple[Profile, ...]
    inspections: tuple[StoreInspection, ...]
    records_root: str
