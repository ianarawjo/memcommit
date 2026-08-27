"""Shared process-local form model for an editable proposed command."""

from __future__ import annotations

import shlex
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from memcommit.application.exact_command_review import ExactCommandReview
from memcommit.adapters.interfaces.console.text import display_escape_text
from memcommit.adapters.interfaces.tui.components.exact_command_review.rendering import (
    format_exact_command,
)


@dataclass(frozen=True)
class ExactCommandFormField:
    """One operand or flag row shown below an editable command."""

    syntax: str
    description: str

    def __post_init__(self) -> None:
        for value, label in (
            (self.syntax, "Command-form syntax"),
            (self.description, "Command-form description"),
        ):
            if (
                not isinstance(value, str)
                or not value.strip()
                or any(character in value for character in "\r\n")
            ):
                raise ValueError(f"{label} must be nonempty one-line text.")


@dataclass(frozen=True)
class ExactCommandForm:
    """Operation-owned command grammar projected through common TUI chrome."""

    command: tuple[str, ...]
    usage: str
    fields: tuple[ExactCommandFormField, ...]

    def __post_init__(self) -> None:
        if (
            not self.command
            or any(not isinstance(value, str) or not value for value in self.command)
        ):
            raise ValueError("Command forms require a nonempty command prefix.")
        if (
            not isinstance(self.usage, str)
            or not self.usage.strip()
            or any(character in self.usage for character in "\r\n")
        ):
            raise ValueError("Command-form usage must be nonempty one-line text.")
        if not self.fields or any(
            not isinstance(field, ExactCommandFormField) for field in self.fields
        ):
            raise ValueError("Command forms require at least one typed field.")

    def parse(self, text: str) -> tuple[str, ...]:
        """Parse one shell-like line and retain the operation boundary."""

        if not isinstance(text, str) or not text.strip():
            raise ValueError("Proposed command must be nonempty text.")
        if any(character in text for character in "\r\n"):
            raise ValueError("Proposed command must stay on one line.")
        try:
            argv = tuple(shlex.split(text))
        except ValueError as error:
            raise ValueError(f"Proposed command has invalid quoting: {error}") from error
        if argv[: len(self.command)] != self.command:
            expected = shlex.join(self.command)
            raise ValueError(f"This form edits only '{expected}'.")
        return argv


class ExactCommandDraft:
    """Synchronize one command line with operation-owned interactive state.

    The common draft owns parsing and live validity.  Its callback may update
    process-local controls only; durable application remains the calling
    operation's separate approval action.
    """

    def __init__(
        self,
        *,
        review: Callable[[], ExactCommandReview],
        apply_argv: Callable[[tuple[str, ...]], None],
        form: ExactCommandForm,
    ) -> None:
        if not callable(review) or not callable(apply_argv):
            raise TypeError("Editable commands require review and Apply callbacks.")
        if not isinstance(form, ExactCommandForm):
            raise TypeError("Editable commands require an ExactCommandForm.")
        self._review = review
        self._apply_argv = apply_argv
        self.form = form
        self.error = ""
        self.valid = False

    def review(self) -> ExactCommandReview:
        value = self._review()
        if not isinstance(value, ExactCommandReview):
            raise TypeError("Proposed-command review returned an invalid receipt.")
        return value

    def command_line(self) -> str:
        return format_exact_command(self.review())

    def synchronize(self, text: str) -> bool:
        """Apply a complete valid line immediately, or retain one local error.

        Operation adapters validate the complete request before moving any
        process-local controls.  That all-or-none boundary is why incomplete
        keystrokes can remain visible without partially changing the form.
        """

        try:
            argv = self.form.parse(text)
            self._apply_argv(argv)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
            self.error = str(error)
            self.valid = False
            return False
        self.error = ""
        self.valid = True
        return True

    def accept_review(self) -> str:
        """Record the current operation-owned review as a valid command line."""

        line = self.command_line()
        self.error = ""
        self.valid = True
        return line

    def reject_review(self, error: Exception) -> str:
        """Expose an incomplete upper form as an invalid editable seed."""

        self.error = str(error)
        self.valid = False
        return shlex.join(self.form.command) + " "

def shortest_unique_identifier_prefix(
    value: str,
    candidates: Sequence[str],
    *,
    minimum: int = 7,
) -> str:
    """Return the shortest collision-safe prefix at or above ``minimum``.

    This helper is intentionally opt-in.  Arbitrary command arguments and
    opaque plan digests must never be abbreviated merely because they resemble
    an identifier.
    """

    values = tuple(dict.fromkeys(candidates))
    if (
        not isinstance(value, str)
        or not value
        or value not in values
        or isinstance(minimum, bool)
        or not isinstance(minimum, int)
        or minimum < 1
    ):
        raise ValueError("Identifier prefix requires a candidate and positive width.")
    width = min(minimum, len(value))
    while width < len(value) and any(
        candidate != value and candidate.startswith(value[:width])
        for candidate in values
    ):
        width += 1
    return value[:width]


def resolve_displayed_command_value(
    value: str,
    candidates: Sequence[str],
    *,
    label: str,
) -> str:
    """Resolve raw or terminal-escaped text to one frozen catalog value."""

    values = tuple(dict.fromkeys(candidates))
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be nonempty text.")
    matches = tuple(
        candidate
        for candidate in values
        if value == candidate or value == display_escape_text(candidate)
    )
    if not matches:
        raise ValueError(
            f"{label} is not available in this review. "
            "Reopen the operation and select it again."
        )
    if len(matches) > 1:
        raise ValueError(f"{label} is ambiguous after terminal escaping.")
    return matches[0]


__all__ = [
    "ExactCommandDraft",
    "ExactCommandForm",
    "ExactCommandFormField",
    "resolve_displayed_command_value",
    "shortest_unique_identifier_prefix",
]
