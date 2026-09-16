"""Core state transitions for bounded current-Context navigation history."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal


ContextNavigationDirection = Literal["PREVIOUS", "NEXT"]

CONTEXT_NAVIGATION_STATE_KEY = "context_navigation"
CONTEXT_NAVIGATION_HISTORY_LIMIT = 64


class ContextNavigationError(ValueError):
    """Persisted navigation state or a requested traversal is invalid."""


def _context_name(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContextNavigationError(f"{field} is invalid.")
    return value


def _history(value: object, *, field: str) -> list[str]:
    if not isinstance(value, list):
        raise ContextNavigationError(f"Context navigation {field} is invalid.")
    if len(value) > CONTEXT_NAVIGATION_HISTORY_LIMIT:
        raise ContextNavigationError(
            f"Context navigation {field} exceeds its retained-history limit."
        )
    return [
        _context_name(item, field=f"Context navigation {field} entry") for item in value
    ]


def read_context_navigation(
    state: dict[str, object],
) -> tuple[list[str], list[str]]:
    """Return validated back/forward stacks, accepting legacy state lazily."""

    raw = state.get(CONTEXT_NAVIGATION_STATE_KEY)
    if raw is None:
        return [], []
    if not isinstance(raw, dict) or set(raw) != {"version", "back", "forward"}:
        raise ContextNavigationError("Context navigation state is invalid.")
    if raw.get("version") != 1:
        raise ContextNavigationError("Context navigation version is unsupported.")
    return (
        _history(raw.get("back"), field="back history"),
        _history(raw.get("forward"), field="forward history"),
    )


def _write_context_navigation(
    state: dict[str, object],
    *,
    back: list[str],
    forward: list[str],
) -> None:
    state[CONTEXT_NAVIGATION_STATE_KEY] = {
        "version": 1,
        "back": back[-CONTEXT_NAVIGATION_HISTORY_LIMIT:],
        "forward": forward[-CONTEXT_NAVIGATION_HISTORY_LIMIT:],
    }


def record_current_context_transition(
    state: dict[str, object],
    target_name: str | None,
) -> None:
    """Append one direct pointer transition and clear its forward branch."""

    current = state.get("current")
    if current is not None:
        current = _context_name(current, field="Current Context state")
    if target_name is not None:
        _context_name(target_name, field="Target Context name")
    if current == target_name:
        return
    back, _forward = read_context_navigation(state)
    if current is not None:
        back.append(current)
    state["current"] = target_name
    _write_context_navigation(state, back=back, forward=[])


def context_navigation_target(
    state: dict[str, object],
    direction: ContextNavigationDirection,
) -> str:
    """Return the next exact history target without mutating the state."""

    back, forward = read_context_navigation(state)
    if direction == "PREVIOUS":
        if not back:
            raise ContextNavigationError("No previous Context is available.")
        return back[-1]
    if direction == "NEXT":
        if not forward:
            raise ContextNavigationError("No next Context is available.")
        return forward[-1]
    raise ContextNavigationError("Context navigation direction is invalid.")


def apply_context_navigation(
    state: dict[str, object],
    *,
    direction: ContextNavigationDirection,
    target_name: str,
) -> None:
    """Move one exact stack entry after a caller has validated its target."""

    expected_target = context_navigation_target(state, direction)
    if expected_target != target_name:
        raise ContextNavigationError(
            "Context navigation changed before it could be selected."
        )
    current = state.get("current")
    if current is not None:
        current = _context_name(current, field="Current Context state")
    back, forward = read_context_navigation(state)
    if direction == "PREVIOUS":
        back.pop()
        if current is not None:
            forward.append(current)
    else:
        forward.pop()
        if current is not None:
            back.append(current)
    state["current"] = target_name
    _write_context_navigation(state, back=back, forward=forward)


def rewrite_context_navigation_names(
    state: dict[str, object],
    mapper: Callable[[str], str],
) -> None:
    """Rewrite retained names during an identity-preserving Context rename."""

    back, forward = read_context_navigation(state)
    if not back and not forward and CONTEXT_NAVIGATION_STATE_KEY not in state:
        return
    mapped_back = [mapper(name) for name in back]
    mapped_forward = [mapper(name) for name in forward]
    for name in (*mapped_back, *mapped_forward):
        _context_name(name, field="Mapped Context navigation entry")
    _write_context_navigation(
        state,
        back=mapped_back,
        forward=mapped_forward,
    )
