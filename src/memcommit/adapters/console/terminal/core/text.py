"""Terminal-safe text transformations shared by CLI and TUI adapters."""

from __future__ import annotations

import unicodedata


def safe_terminal_text(value: str) -> str:
    """Replace terminal controls while retaining explicit newline/tab layout."""

    result: list[str] = []
    for character in value:
        if character in {"\n", "\t"}:
            result.append(character)
        elif unicodedata.category(character).startswith("C") or unicodedata.category(
            character
        ) in {"Zl", "Zp"}:
            result.append("�")
        else:
            result.append(character)
    return "".join(result)


def display_escape_text(value: str) -> str:
    """Return an injective, single-line representation of untrusted text."""

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
