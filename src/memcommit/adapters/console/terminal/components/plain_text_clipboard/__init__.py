"""Plain operating-system clipboard projection for read-only TUI surfaces."""

from memcommit.adapters.console.terminal.components.plain_text_clipboard.component import (
    ClipboardWriter,
    PlainTextClipboardReceipt,
    clipboard_failure_receipt,
    copy_plain_text,
)
from memcommit.adapters.console.terminal.components.plain_text_clipboard.projection import (
    FormattedFragments,
    plain_text_from_fragments,
)

__all__ = [
    "ClipboardWriter",
    "FormattedFragments",
    "PlainTextClipboardReceipt",
    "clipboard_failure_receipt",
    "copy_plain_text",
    "plain_text_from_fragments",
]
