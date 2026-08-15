"""Neutral rendering for a frozen exact command review."""

from __future__ import annotations

import shlex

from memcommit.exact_command_review import ExactCommandReview
from memcommit.interfaces.console.text import display_escape_text


def format_exact_command(review: ExactCommandReview) -> str:
    """Render argv as one unambiguous, non-executable display line."""

    return shlex.join(
        tuple(display_escape_text(argument) for argument in review.argv)
    )


def render_exact_command_blocks(
    review: ExactCommandReview,
) -> tuple[str, str]:
    """Return separate command and effect blocks for viewport anchoring."""

    command = "\n".join(
        [
            "PROPOSED COMMAND · NOT RUN",
            f"  {format_exact_command(review)}",
        ]
    )
    effects = "\n".join(
        [
            "EFFECTS · ONE COMMAND",
            *[
                f"  {display_escape_text(effect)}"
                for effect in review.effects
            ],
            "",
            "Approval applies only to the exact command shown above.",
        ]
    )
    return command, effects


def render_exact_command_review(review: ExactCommandReview) -> str:
    """Render a complete exact-command approval receipt."""

    return "\n\n".join(render_exact_command_blocks(review))
