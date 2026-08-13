"""Operation-neutral review model for one exact, locally built CLI command."""
from __future__ import annotations

import shlex
from dataclasses import dataclass

from memcommit.interfaces.console.text import display_escape_text


@dataclass(frozen=True)
class ExactCommandReview:
    """A frozen argv and its complete user-facing mutation boundary."""

    argv: tuple[str, ...]
    effects: tuple[str, ...]

    def __post_init__(self) -> None:
        # ``frozen=True`` prevents attribute reassignment but would still let a
        # caller mutate a list after it had been displayed for approval.  Copy
        # both inputs into tuples so the reviewed command remains the command
        # that can later be executed.
        if isinstance(self.argv, (str, bytes)) or isinstance(
            self.effects,
            (str, bytes),
        ):
            raise ValueError("Exact command review requires argv sequences.")
        try:
            object.__setattr__(self, "argv", tuple(self.argv))
            object.__setattr__(self, "effects", tuple(self.effects))
        except TypeError as error:
            raise ValueError(
                "Exact command review requires argv sequences."
            ) from error
        if not self.argv or any(not isinstance(arg, str) for arg in self.argv):
            raise ValueError("Exact command review requires a non-empty argv.")
        if not self.effects or any(
            not isinstance(effect, str) or not effect.strip()
            for effect in self.effects
        ):
            raise ValueError(
                "Exact command review requires non-empty effect lines."
            )


def format_exact_command(review: ExactCommandReview) -> str:
    """Render frozen argv as one unambiguous, non-executable display line."""
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
