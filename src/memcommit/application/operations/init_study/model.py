"""Typed results published by the init-study application."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from memcommit.application.operations.profile.config import ProfileEntry

if TYPE_CHECKING:
    from memcommit.application.operations.profile.model import StoreInspection


@dataclass(frozen=True)
class StudyInitializationResult:
    """One isolated participant/authority pair copied from a Study baseline."""

    profile: ProfileEntry
    inspection: StoreInspection
    authority_profile: ProfileEntry
    authority_inspection: StoreInspection
    baseline_profile_name: str
    active_profile_name: str
    scenario_id: str = "legacy-v1"
    declared_compare_prewarms: int = 0
    installed_compare_prewarms: int = 0
    skipped_compare_prewarms: int = 0
    declared_atomize_prewarms: int = 0
    installed_atomize_prewarms: int = 0
    skipped_atomize_prewarms: int = 0
    declared_summarize_prewarms: int = 0
    installed_summarize_prewarms: int = 0
    skipped_summarize_prewarms: int = 0
    declared_update_prewarms: int = 0
    installed_update_prewarms: int = 0
    skipped_update_prewarms: int = 0
    declared_sever_prewarms: int = 0
    installed_sever_prewarms: int = 0
    skipped_sever_prewarms: int = 0
    declared_directional_meld_prewarms: int = 0
    installed_directional_meld_prewarms: int = 0
    skipped_directional_meld_prewarms: int = 0
    declared_meld_resolution_prewarms: int = 0
    installed_meld_resolution_prewarms: int = 0
    skipped_meld_resolution_prewarms: int = 0
    installed_meld_resolution_branches: int = 0
