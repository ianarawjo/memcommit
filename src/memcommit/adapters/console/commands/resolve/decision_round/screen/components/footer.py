"""Footer for the decision screen."""

from __future__ import annotations

from time import monotonic

from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.terminal.core.activity import (
    BUSY_INTERVAL_SECONDS,
    busy_suffix,
)


def render_footer(state, *, intent=None, is_focused, activation_hint) -> str:
    if intent is not None and intent.pending:
        frame = int((monotonic() - intent.started_at) / BUSY_INTERVAL_SECONDS)
        return " Preparing your intent preview " + busy_suffix(frame)
    if is_focused("navigation"):
        return " ← PREV / NEXT → issue · →/← switch button · Enter open issue · ↓ choices · Tab return · Esc close"
    if state.status_message:
        return " " + safe_terminal_text(state.status_message)
    if intent is not None and is_focused("intent"):
        if intent.prepare is not None:
            return " Type your intent · Enter refresh result · ↑/↓ or Tab choices · PgUp/PgDn result · Esc choices"
        return " Type your intent · ←/→ cursor · Enter save · ↑/↓ or Tab choices · Esc choices"
    return (
        " ←/→ issue · ↑/↓ move · Enter "
        + safe_terminal_text(activation_hint)
        + " · PgUp/PgDn read"
        + (" · Tab navigation" if state.navigation_visible else "")
        + " · Esc close"
    )
