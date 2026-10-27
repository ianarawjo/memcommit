"""Values returned by current Study Profile-group administration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from memcommit.models.profile import Profile


@dataclass(frozen=True)
class StudyRunProfileGroup:
    """The registered sessions of one Study, including partially removed runs."""

    uid: str
    name: str
    created_at: str
    profiles: tuple[Profile, ...]


@dataclass(frozen=True)
class StudyRenameResult:
    """One stable Study identity published under a new display name."""

    uid: str
    previous_name: str
    name: str
    profiles: tuple[Profile, ...]
    active_profile_name: str
    changed: bool


@dataclass(frozen=True)
class StudyRemovalResult:
    """One complete Study whose Profile stores were permanently deleted."""

    uid: str
    name: str
    profiles: tuple[Profile, ...]
    newly_removed_count: int
    deleted_stores: tuple[Path, ...]
    active_profile_name: str
