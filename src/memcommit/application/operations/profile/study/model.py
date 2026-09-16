"""Values returned by current Study Profile-pair administration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from memcommit.application.operations.profile.config import ProfileEntry


@dataclass(frozen=True)
class StudyRunProfilePair:
    """One current ``init-study`` participant/authority Profile pair."""

    uid: str
    name: str
    created_at: str
    participant: ProfileEntry
    authority: ProfileEntry


@dataclass(frozen=True)
class StudyRenameResult:
    """One stable Study identity published under a new display name."""

    uid: str
    previous_name: str
    name: str
    profiles: tuple[ProfileEntry, ...]
    active_profile_name: str
    changed: bool


@dataclass(frozen=True)
class StudyRemovalResult:
    """One complete Study whose Profile stores were permanently deleted."""

    uid: str
    name: str
    profiles: tuple[ProfileEntry, ...]
    newly_removed_count: int
    removed_grant_count: int
    deleted_stores: tuple[Path, ...]
    active_profile_name: str
