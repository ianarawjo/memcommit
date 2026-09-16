"""Typed results published by the init-study application."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from memcommit.application.operations.profile.config import ProfileEntry

if TYPE_CHECKING:
    from memcommit.application.operations.profile.model import StoreInspection


@dataclass(frozen=True)
class StudyInitializationResult:
    """One isolated participant/authority pair built from a Study scenario."""

    profile: ProfileEntry
    inspection: StoreInspection
    authority_profile: ProfileEntry
    authority_inspection: StoreInspection
    active_profile_name: str
    scenario_id: str = "legacy"
