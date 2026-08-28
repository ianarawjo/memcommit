"""Render Ground entry, snapshot, and focused inspection views."""

from __future__ import annotations

from memcommit.adapters.console.terminal.core.text import safe_terminal_text

from . import create as create_workflow
from .session.inspect import render_ground_focus, render_ground_snapshot

__all__ = ["render_ground_focus", "render_ground_snapshot", "render_ground_start"]


def render_ground_start(initial_request: str = "") -> str:
    """Render the unsaved entry frame for a blank grounding conversation."""
    working_goal = (
        create_workflow._validated_start_request(initial_request)
        if initial_request
        else ""
    )
    safe_goal = safe_terminal_text(working_goal).replace("\n", "\n  ")
    goal_lines = ["  (not yet stated)"] if not safe_goal else [f"  {safe_goal}"]
    dialogue_lines = (
        [
            "OPEN QUESTION · GOAL",
            "  What are you trying to understand, decide, or make together?",
            "",
            "  Start in your own words. You do not need a Ground name,",
            "  Rules, Memories, or final wording yet.",
            "",
            "  A rough outcome, concrete example, or uncertainty is enough.",
        ]
        if not safe_goal
        else [
            "CHAT",
            "  YOU · STARTING REQUEST",
            f"  {safe_goal}",
            "",
            "  Run this command in an interactive terminal to interpret",
            "  the Working Goal and continue the chat.",
        ]
    )
    return "\n".join(
        [
            "MEM GROUND · DRAFT",
            "",
            "GOAL",
            *goal_lines,
            "",
            "CONTEXTS",
            "  (none selected)",
            "  No current Context was read.",
            "",
            "RULES",
            "  (none yet)",
            "",
            "MEMORIES",
            "  (none yet)",
            "",
            *dialogue_lines,
            "",
            "DESCRIBE WHAT YOU HAVE SO FAR",
            "",
            "> ________________________________________________________________",
            (
                "  Reply to the agent; this snapshot does not read stdin."
                if not safe_goal
                else (
                    "  In a TTY, this submitted request starts the agent's "
                    "Context discovery turn."
                )
            ),
            "",
            "NEXT",
            "  The agent will confirm the Goal and portable GROUND_NAME,",
            "  compare name-only Contexts, and may show one NEW? Context",
            "  plus unsaved Rule and Memory drafts.",
            "  Only the exact mem ground creation command can be approved.",
            "  Nothing is created until you approve that command.",
            "",
            "No Ground has been created.",
            "No Context or Context Memory changes have been applied.",
            "No checkpoint has been created.",
        ]
    )
