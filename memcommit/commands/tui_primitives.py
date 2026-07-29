"""Small presentation primitives shared by memcommit terminal workbenches.

This module deliberately owns terminal mechanics, not semantic state,
provider prompts, persistence, or operation-specific key meanings.
"""
from __future__ import annotations

import sys
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from prompt_toolkit.layout import HSplit, Window
from prompt_toolkit.layout.containers import AnyContainer


@dataclass(frozen=True)
class TuiRegion:
    """One vertical shell region and its presentation boundary."""

    container: AnyContainer
    separator_before: bool = False


def build_tui_frame(*regions: TuiRegion) -> HSplit:
    """Compose operation-owned regions into one full-screen vertical frame."""
    children: list[AnyContainer] = []
    for region in regions:
        if region.separator_before:
            children.append(Window(height=1, char="─"))
        children.append(region.container)
    return HSplit(children)


def require_interactive_terminal(
    operation: str,
    *,
    snapshot_hint: str = "",
) -> None:
    """Fail before opening a full-screen application outside a TTY."""
    if sys.stdin.isatty() and sys.stdout.isatty():
        return
    message = f"{operation} requires a TTY (interactive terminal)."
    if snapshot_hint:
        message += f" {snapshot_hint}"
    raise ValueError(message)


def safe_terminal_text(value: str) -> str:
    """Replace terminal controls while retaining explicit newline/tab layout."""
    result: list[str] = []
    for character in value:
        if character in {"\n", "\t"}:
            result.append(character)
        elif (
            unicodedata.category(character).startswith("C")
            or unicodedata.category(character) in {"Zl", "Zp"}
        ):
            result.append("�")
        else:
            result.append(character)
    return "".join(result)


def display_escape_text(value: str) -> str:
    """Return an injective, single-line representation of untrusted text.

    Exact-command receipts use this stricter boundary because preserving a
    newline, tab, bidi override, or zero-width format character there could
    make one argument look like a second command or a trusted UI heading.
    Backslashes are escaped first so every visible escape remains
    unambiguous; normal printable text, including Korean, stays readable.
    """
    escaped: list[str] = []
    named_controls = {
        "\n": r"\n",
        "\t": r"\t",
        "\r": r"\r",
        "\b": r"\b",
        "\f": r"\f",
        "\v": r"\v",
    }
    for character in value:
        if character == "\\":
            escaped.append(r"\\")
            continue
        if character in named_controls:
            escaped.append(named_controls[character])
            continue
        category = unicodedata.category(character)
        if category.startswith("C") or category in {"Zl", "Zp"}:
            codepoint = ord(character)
            if codepoint <= 0xFF:
                escaped.append(f"\\x{codepoint:02x}")
            elif codepoint <= 0xFFFF:
                escaped.append(f"\\u{codepoint:04x}")
            else:
                escaped.append(f"\\U{codepoint:08x}")
            continue
        escaped.append(character)
    return "".join(escaped)


def anchored_fragments(
    blocks: Sequence[str],
    *,
    anchor_index: int | None,
    anchor_at_end: bool = False,
) -> list[tuple[str, str]]:
    """Render text blocks with one prompt-toolkit viewport anchor.

    A caller chooses the semantically active block. Anchoring after an exact
    command keeps all of that command's wrapped logical line visible whenever
    it fits, while errors and selected issues normally anchor at their start.
    """
    fragments: list[tuple[str, str]] = []
    for index, block in enumerate(blocks):
        if index:
            fragments.append(("", "\n\n"))
        if index == anchor_index and not anchor_at_end:
            fragments.append(("[SetCursorPosition]", ""))
        fragments.append(("", block))
        if index == anchor_index and anchor_at_end:
            fragments.append(("[SetCursorPosition]", ""))
    if anchor_index is None:
        fragments.append(("[SetCursorPosition]", ""))
    return fragments
