"""Resolve and freeze Store paths for one Store instance."""

from __future__ import annotations
import os
from pathlib import Path
from memcommit.application.operations.profile.config import resolve_active_store_dir
from memcommit.persistence.store.infrastructure.storage_permissions import (
    ensure_private_directory,
)


class _ActiveStorePath(os.PathLike[str]):
    """Compatibility path that defers active-Profile I/O until path use."""

    __slots__ = ("_parts",)
    __hash__ = None

    def __init__(self, *parts: str) -> None:
        self._parts = parts

    def _resolve(self) -> Path:
        return resolve_active_store_dir().joinpath(*self._parts)

    def __fspath__(self) -> str:
        return os.fspath(self._resolve())

    def __str__(self) -> str:
        return str(self._resolve())

    def __repr__(self) -> str:
        return f"_ActiveStorePath({self._resolve()!r})"

    def __truediv__(self, child: str | os.PathLike[str]) -> Path:
        return self._resolve() / child

    def __eq__(self, other: object) -> bool:
        try:
            return self._resolve() == Path(other)  # type: ignore[arg-type]
        except TypeError:
            return False

    def __getattr__(self, name: str):
        return getattr(self._resolve(), name)


STORE_DIR = _ActiveStorePath()
CONTEXTS_DIR = _ActiveStorePath("contexts")
STATE_FILE = _ActiveStorePath("state.json")
IMPACT_PLAN_FILE = _ActiveStorePath("impact-plan.json")
STAGED_UPDATE_FILE = _ActiveStorePath("staged-update.json")
REVIEW_SESSION_FILE = _ActiveStorePath("review-session.json")
REVIEW_SESSION_HISTORY_DIR = _ActiveStorePath("review-session-history")
REVIEW_SESSION_SOURCES_DIR = _ActiveStorePath("review-session-sources")
ATOMIZE_ANALYSES_DIR = _ActiveStorePath("atomize-analyses")
ATOMIZE_WORKBENCHES_DIR = _ActiveStorePath("atomize-workbenches")
ATOMIZE_SESSION_HISTORY_DIR = _ActiveStorePath("atomize-session-history")


class _StorePathsMixin:
    """Focused slice of the temporary Store assembly."""

    def __init__(
        self,
        *,
        create: bool = True,
        root: Path | None = None,
    ):
        """
        Open the store.

        Normal commands create missing store infrastructure. Read-only
        inspection commands can pass create=False to guarantee that merely
        checking absent state does not create a Profile Store or state.json. ``root``
        is an explicit store boundary; omitting it resolves and freezes the
        active Profile now.
        """
        # Explicit roots are already selected by the caller and must not touch
        # HOME Profile state. Profile-backed stores resolve exactly once here
        # so a later process-global Profile switch cannot retarget this object.
        self._store_dir = Path(root).absolute() if root is not None else Path(STORE_DIR)
        if create:
            ensure_private_directory(self.store_dir, parents=True)
            if root is None:
                from memcommit.application.operations.profile.config import (
                    load_profile_registry,
                    profile_store_dir,
                )
                from memcommit.application.operations.profile.project_root import (
                    write_profile_marker,
                    validate_profile_marker,
                )

                profile = load_profile_registry().active
                if profile_store_dir(profile).resolve() == self.store_dir.resolve():
                    if (self.store_dir / "profile.json").exists():
                        validate_profile_marker(profile)
                    else:
                        write_profile_marker(self.store_dir, profile.uid)
            ensure_private_directory(self.contexts_dir, parents=True)
            if not self.state_file.exists():
                self._write_state({"current": None})

    @property
    def store_dir(self) -> Path:
        return self._store_dir

    @property
    def contexts_dir(self) -> Path:
        return self.store_dir / "contexts"

    @property
    def state_file(self) -> Path:
        return self.store_dir / "state.json"

    @property
    def impact_plan_file(self) -> Path:
        return self.store_dir / "impact-plan.json"

    @property
    def staged_update_file(self) -> Path:
        return self.store_dir / "staged-update.json"

    @property
    def review_session_file(self) -> Path:
        return self.store_dir / "review-session.json"

    @property
    def review_session_history_dir(self) -> Path:
        return self.store_dir / "review-session-history"

    @property
    def review_session_sources_dir(self) -> Path:
        return self.store_dir / "review-session-sources"

    @property
    def command_context_archives_dir(self) -> Path:
        """Private retained histories for undo of Context-creation commands."""
        return self.store_dir / "command-context-archives"

    @property
    def atomize_analyses_dir(self) -> Path:
        return self.store_dir / "atomize-analyses"

    @property
    def atomize_workbenches_dir(self) -> Path:
        return self.store_dir / "atomize-workbenches"

    @property
    def atomize_session_history_dir(self) -> Path:
        return self.store_dir / "atomize-session-history"
