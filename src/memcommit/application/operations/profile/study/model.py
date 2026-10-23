"""Values returned by current Study Profile-group administration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from memcommit.models.profile import Profile


@dataclass(frozen=True)
class StudyRunProfileGroup:
    """The local Profile registered for one ``init-study`` run."""

    uid: str
    name: str
    created_at: str
    participant: Profile

    @property
    def profiles(self) -> tuple[Profile, ...]:
        return (self.participant,)


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
