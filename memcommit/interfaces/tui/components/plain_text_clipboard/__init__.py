"""Plain operating-system clipboard projection for read-only TUI surfaces."""

from memcommit.interfaces.tui.components.plain_text_clipboard.component import (
    ClipboardWriter,
    PlainTextClipboardReceipt,
    clipboard_failure_receipt,
    copy_plain_text,
)

__all__ = [
    "ClipboardWriter",
    "PlainTextClipboardReceipt",
    "clipboard_failure_receipt",
    "copy_plain_text",
]
