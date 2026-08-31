"""Compact terminal receipt for one applied direct Update."""

from __future__ import annotations

from memcommit.application.operations.update.model import (
    UpdateSession,
    count_operations,
)


def render_update_receipt(session: UpdateSession) -> str:
    """Render terminal Update success without reopening its full report."""

    if session.status != "applied" or session.application is None:
        raise ValueError("Update receipt requires an applied session.")
    edits, additions, removals = count_operations(session)
    checkpoints = session.application.checkpoints
    lines = [
        f"UPDATE APPLIED · {session.source_name} → {session.target_name}",
        f"EFFECTS · ADD {additions} · EDIT {edits} · REMOVE {removals}",
        f"RECEIPT · {session.uid}",
    ]
    if not session.operations:
        lines.insert(1, "OUTCOME · NO CHANGE · no Context checkpoint")
    if session.goal_focus is not None:
        lines.append(
            "GOAL FOCUS · "
            f"{session.goal_focus.kind} · {session.goal_focus.label} · "
            f"{len(session.goal_focus.items)} ITEM"
            f"{'S' if len(session.goal_focus.items) != 1 else ''}"
        )
    if checkpoints:
        lines.append(
            "CHECKPOINTS · "
            + " · ".join(
                f"{item.context_name} [{item.checkpoint_uid}]" for item in checkpoints
            )
        )
    lines.append(f"REVIEW · mem review update --session {session.uid}")
    if session.granted_target is None and checkpoints:
        lines.append("RECOVERY · mem undo")
    elif session.granted_target is not None:
        lines.append("RECOVERY · governed by the granted authority owner")
    return "\n".join(lines)


__all__ = ["render_update_receipt"]
