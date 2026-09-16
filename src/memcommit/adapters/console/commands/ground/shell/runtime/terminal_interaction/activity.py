"""Pane-local projection of Ground drafting activity."""

from __future__ import annotations

from memcommit.adapters.console.terminal.core.text import safe_terminal_text

from memcommit.adapters.console.commands.ground.shell.runtime.session.state import (
    GroundPane,
    GroundPaneActivity,
)


def pane_turn_label(target: GroundPane) -> str:
    return {
        "LOCATION": "SAVE LOCATION",
        "GOAL": "GOAL REVISION REQUEST",
        "CONTEXTS": "WORKSPACE REVISION REQUEST",
        "RULES": "RULE REVISION REQUEST",
        "MEMORIES": "MEMORY REVISION REQUEST",
        "CHAT": "MESSAGE",
    }[target]


def pane_thinking_verb(target: GroundPane) -> str:
    return {
        "LOCATION": "CHOOSING",
        "GOAL": "REVISING",
        "CONTEXTS": "RECONSIDERING",
        "RULES": "REVISING",
        "MEMORIES": "REVISING",
        "CHAT": "RESPONDING",
    }[target]


def pane_activity_text(
    target: GroundPane,
    base: str,
    activity: GroundPaneActivity,
) -> str:
    """Keep a focused semantic turn in the pane that originated it."""

    if activity.phase == "IDLE" or target == "CHAT":
        return base
    if activity.phase == "THINKING":
        heading = f"{pane_turn_label(target)} · SUBMITTED"
    elif activity.phase == "PROPOSED":
        heading = f"PROPOSED {target} REVISION"
    elif activity.phase == "NEEDS_CLARIFICATION":
        heading = f"{target} REVISION · NEEDS CLARIFICATION"
    else:
        heading = f"{target} REVISION · FAILED · NOTHING APPLIED"
    lines = [heading]
    if activity.phase == "PROPOSED":
        # A compact Goal viewport must show the revised semantic value before
        # its provenance so a successful revision does not look unchanged.
        visible_result = base.removeprefix("PROPOSED\n") if target == "GOAL" else base
        lines.append(visible_result)
        if activity.request:
            lines.extend(["", "REQUEST", safe_terminal_text(activity.request)])
        return "\n".join(lines)
    if activity.detail:
        lines.extend([safe_terminal_text(activity.detail), ""])
    if activity.request:
        lines.extend(["REQUEST", safe_terminal_text(activity.request), ""])
    lines.append(base)
    return "\n".join(lines)
