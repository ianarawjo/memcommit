"""Typed results published by the init-study application."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from memcommit.models.profile import Profile

if TYPE_CHECKING:
    from memcommit.application.operations.profile.model import StoreInspection


@dataclass(frozen=True)
class StudyInitializationResult:
    """One isolated local Profile built from a Study scenario."""

    profile: Profile
    inspection: StoreInspection
    active_profile_name: str
    scenario_id: str = "legacy"
