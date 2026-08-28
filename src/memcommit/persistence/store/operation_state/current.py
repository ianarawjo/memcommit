"""Persist the active Context selection and navigation state."""

from __future__ import annotations
import json
from typing import Optional
from memcommit.core.context_targeting.navigation import (
    ContextNavigationDirection,
    apply_context_navigation,
    context_navigation_target,
    record_current_context_transition,
)


from ..context_memory.models import (
    ConcurrentContextUpdateError,
)
from ..context_memory.records import (
    _context_name_parts,
    context_record_digest,
)
from ..infrastructure.atomic_io import (
    _write_json_atomic,
)


class _CurrentStateStoreMixin:
    """Focused slice of the temporary Store assembly."""

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

    def context_navigation_target(
        self,
        expected_current: str | None,
        direction: ContextNavigationDirection,
    ) -> str:
        """Freeze one exact back/forward destination for later CAS publication."""

        state = self._read_state()
        if state.get("current") != expected_current:
            raise ConcurrentContextUpdateError(
                "The current Context changed before it could be switched."
            )
        return context_navigation_target(state, direction)

    def set_current(self, name: str) -> None:
        with self._context_graph_lock(exclusive=False):
            with self._context_write_lock(name):
                if not self.context_exists(name):
                    raise FileNotFoundError(f"Context '{name}' not found.")
                with self._state_write_lock():
                    state = self._read_state()
                    record_current_context_transition(state, name)
                    self._write_state(state)

    def set_current_context_if(
        self,
        expected_current: str | None,
        name: str,
        *,
        expected_context_uid: str,
        expected_context_digest: str,
        navigation_direction: ContextNavigationDirection | None = None,
    ) -> None:
        """CAS-switch to one exact Context while blocking save/delete/recreate."""
        if (
            not isinstance(expected_context_digest, str)
            or len(expected_context_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in expected_context_digest
            )
        ):
            raise ValueError("Expected Context digest is invalid.")
        with self._context_graph_lock(exclusive=False):
            with self._context_write_lock(name):
                if not self.context_exists(name):
                    raise ConcurrentContextUpdateError(
                        f"Context '{name}' no longer exists."
                    )
                target = self.load_direct(name)
                if (
                    target.uid != expected_context_uid
                    or context_record_digest(target) != expected_context_digest
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
                    if navigation_direction is None:
                        record_current_context_transition(state, name)
                    else:
                        apply_context_navigation(
                            state,
                            direction=navigation_direction,
                            target_name=name,
                        )
                    self._write_state(state)

    def set_current_virtual_context_if(
        self,
        expected_current: str | None,
        name: str,
        *,
        navigation_direction: ContextNavigationDirection | None = None,
    ) -> None:
        """CAS-select one externally validated granted Context name.

        A granted view is a navigation pointer, not a locally materialized
        Context. Authorization and authority identity are therefore resolved
        again by each command that consumes the pointer. Only ``mem switch``
        may call this after validating a READ grant; query-only routes remain
        non-selectable.
        """

        _context_name_parts(name)
        if self.context_exists(name):
            raise ValueError(
                f"Context '{name}' is local and must use the ordinary switch path."
            )
        with self._state_write_lock():
            state = self._read_state()
            if state.get("current") != expected_current:
                raise ConcurrentContextUpdateError(
                    "The current Context changed before it could be switched."
                )
            if navigation_direction is None:
                record_current_context_transition(state, name)
            else:
                apply_context_navigation(
                    state,
                    direction=navigation_direction,
                    target_name=name,
                )
            self._write_state(state)
