"""Resolve and freeze Store paths for one Store instance."""

from __future__ import annotations
import os
from pathlib import Path
from memcommit.application.operations.profile.config import resolve_active_store_dir
from memcommit.application.capabilities.authority.storage_permissions import (
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
QUERY_SOURCES_DIR = _ActiveStorePath("query-sources")
IMPACT_PLAN_FILE = _ActiveStorePath("impact-plan.json")
STAGED_UPDATE_FILE = _ActiveStorePath("staged-update.json")
REVIEW_SESSION_FILE = _ActiveStorePath("review-session.json")
REVIEW_SESSION_HISTORY_DIR = _ActiveStorePath("review-session-history")
REVIEW_SESSION_SOURCES_DIR = _ActiveStorePath("review-session-sources")
ATOMIZE_ANALYSES_DIR = _ActiveStorePath("atomize-analyses")
ATOMIZE_WORKBENCHES_DIR = _ActiveStorePath("atomize-workbenches")
ATOMIZE_SESSION_HISTORY_DIR = _ActiveStorePath("atomize-session-history")
ATOMIZE_GROUNDING_SESSIONS_DIR = _ActiveStorePath("atomize-groundings")
ATOMIZE_GROUNDING_HISTORY_DIR = _ActiveStorePath("atomize-grounding-history")
GROUND_SESSIONS_DIR = _ActiveStorePath("ground-sessions")
MELD_SESSIONS_DIR = _ActiveStorePath("meld-sessions")
MELD_SESSION_HISTORY_DIR = _ActiveStorePath("meld-session-history")


class _StorePathsMixin:
    """Focused slice of the temporary Store assembly."""

    def __init__(
        self,
        *,
        create: bool = True,
        root: Path | None = None,
        resolve_granted_links: bool = True,
    ):
        """
        Open the store.

        Normal commands create missing store infrastructure. Read-only
        inspection commands can pass create=False to guarantee that merely
        checking absent state does not create ~/.mem or state.json.  ``root``
        is an explicit, already-authorized store boundary used by profile
        grants; omitting it resolves and freezes the active Profile now.
        ``resolve_granted_links=False`` keeps live granted relationships opaque
        and prevents this Store from consulting process-global Profile state.
        """
        if type(resolve_granted_links) is not bool:
            raise TypeError("resolve_granted_links must be a boolean.")
        # Explicit roots are already selected by the caller and must not touch
        # HOME Profile state. Profile-backed stores resolve exactly once here
        # so a later process-global Profile switch cannot retarget this object.
        self._store_dir = Path(root).absolute() if root is not None else Path(STORE_DIR)
        # Store-root authority and Grant-resolution authority are independent.
        # In particular, a public explicit-root client may inspect a persisted
        # pointer but must not inherit the host process's active Profile Grants.
        self._resolve_granted_links = resolve_granted_links
        if create:
            ensure_private_directory(self.store_dir, parents=True)
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
    def query_sources_dir(self) -> Path:
        return self.store_dir / "query-sources"

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

    @property
    def atomize_grounding_sessions_dir(self) -> Path:
        return self.store_dir / "atomize-groundings"

    @property
    def atomize_grounding_history_dir(self) -> Path:
        return self.store_dir / "atomize-grounding-history"

    @property
    def ground_sessions_dir(self) -> Path:
        return self.store_dir / "ground-sessions"

    @property
    def meld_sessions_dir(self) -> Path:
        return self.store_dir / "meld-sessions"

    @property
    def meld_session_history_dir(self) -> Path:
        return self.store_dir / "meld-session-history"

    @property
    def meld_resolution_branches_dir(self) -> Path:
        """Profile-local exact semantic outcomes for Meld follow-up turns."""
        return self.store_dir / "meld-resolution-branches"

    @property
    def meld_choice_branches_dir(self) -> Path:
        """Provider-free option selections staged for saved Meld sessions."""
        return self.store_dir / "meld-choice-branches"
