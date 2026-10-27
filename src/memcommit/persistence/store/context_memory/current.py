"""Persist the active Context selection."""

from __future__ import annotations
import json
from typing import Optional


from .models import (
    ConcurrentContextUpdateError,
)
from ..infrastructure.atomic_io import (
    _write_json_atomic,
)


class _CurrentContextStoreMixin:
    """Persist the process-visible current Context pointer."""

    def _read_state(self) -> dict:
        with open(self.state_file) as f:
            return json.load(f)

    def _write_state(self, state: dict) -> None:
        # Context switching is the final phase of several multi-file
        # operations.  Replacing an fsynced sibling keeps an interrupted write
        # from leaving state.json truncated and making rollback impossible.
        _write_json_atomic(self.state_file, state)

    def current_context_name(self) -> Optional[str]:
        return self._read_state().get("current")

    def set_current(self, name: str) -> None:
        with self._context_graph_lock(exclusive=False):
            with self._context_write_lock(name):
                if not self.context_exists(name):
                    raise FileNotFoundError(f"Context '{name}' not found.")
                with self._state_write_lock():
                    state = self._read_state()
                    state["current"] = name
                    self._write_state(state)

    def set_current_context_if(
        self,
        expected_current: str | None,
        name: str,
        *,
        expected_context_uid: str,
    ) -> None:
        """Select the reviewed Context identity if the current pointer still matches."""
        with self._context_graph_lock(exclusive=False):
            with self._context_write_lock(name):
                if not self.context_exists(name):
                    raise ConcurrentContextUpdateError(
                        f"Context '{name}' no longer exists."
                    )
                target = self.load_direct(name)
                if (
                    target.uid != expected_context_uid
                ):
                    raise ConcurrentContextUpdateError(
                        f"Context '{name}' changed before it could be selected."
                    )
                with self._state_write_lock():
                    state = self._read_state()
                    if state.get("current") != expected_current:
                        raise ConcurrentContextUpdateError(
                            "The current Context changed before it could be switched."
                        )
                    state["current"] = name
                    self._write_state(state)
