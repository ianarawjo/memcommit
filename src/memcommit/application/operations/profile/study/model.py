"""Values returned by current Study Profile-group administration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from memcommit.application.operations.profile.config import ProfileEntry


@dataclass(frozen=True)
class StudyRunProfileGroup:
    """The remaining registered Profiles in one ``init-study`` run."""

    uid: str
    name: str
    created_at: str
    participant: ProfileEntry | None
    authority: ProfileEntry | None

    @property
    def profiles(self) -> tuple[ProfileEntry, ...]:
        return tuple(
            profile
            for profile in (self.participant, self.authority)
            if profile is not None
        )


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
