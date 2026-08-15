"""Shared plain-text clipboard receipts for read-only semantic TUI surfaces."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from memcommit.clipboard import ClipboardError, write_system_clipboard
from memcommit.interfaces.console.text import (
    display_escape_text,
)


ClipboardWriter = Callable[[str], None]


@dataclass(frozen=True)
class PlainTextClipboardReceipt:
    """One non-durable operating-system clipboard attempt."""

    succeeded: bool
    message: str

    @property
    def style(self) -> str:
        return "class:loading-complete" if self.succeeded else "class:impact.remove"


def clipboard_failure_receipt(error: Exception) -> PlainTextClipboardReceipt:
    """Project a safe failure without exposing terminal control characters."""

    return PlainTextClipboardReceipt(
        False,
        "COPY FAILED · " + display_escape_text(str(error)),
    )


def copy_plain_text(
    text: str,
    *,
    success_message: str,
    writer: ClipboardWriter | None = None,
) -> PlainTextClipboardReceipt:
    """Write one semantic projection without creating a structured stage."""

    if not isinstance(text, str) or not text:
        return clipboard_failure_receipt(
            ValueError("The focused result has no text to copy.")
        )
    try:
        (writer or write_system_clipboard)(text)
    except (ClipboardError, ValueError) as error:
        return clipboard_failure_receipt(error)
    return PlainTextClipboardReceipt(True, f"COPIED · {success_message}")
