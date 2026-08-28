"""Compatibility exports for the interface-owned plain-text clipboard."""

from memcommit.adapters.console.tui.components.plain_text_clipboard import (
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
