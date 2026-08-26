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


def restore_display_escape_text(value: str) -> str:
    """Invert one canonical :func:`display_escape_text` representation.

    Editable single-line command forms use this narrow inverse when an argv
    value represents arbitrary text rather than a catalog identity.  Requiring
    the canonical spelling keeps a literal ``\\n`` distinct from a newline and
    rejects raw terminal controls or ambiguous escape aliases.
    """

    if not isinstance(value, str):
        raise TypeError("Displayed text must be text.")
    named_controls = {
        "n": "\n",
        "t": "\t",
        "r": "\r",
        "b": "\b",
        "f": "\f",
        "v": "\v",
    }
    restored: list[str] = []
    index = 0
    while index < len(value):
        character = value[index]
        if character != "\\":
            restored.append(character)
            index += 1
            continue
        if index + 1 >= len(value):
            raise ValueError("Displayed text ends with an incomplete escape.")
        marker = value[index + 1]
        if marker == "\\":
            restored.append("\\")
            index += 2
            continue
        if marker in named_controls:
            restored.append(named_controls[marker])
            index += 2
            continue
        widths = {"x": 2, "u": 4, "U": 8}
        width = widths.get(marker)
        if width is None:
            raise ValueError("Displayed text contains an unsupported escape.")
        digits = value[index + 2 : index + 2 + width]
        if len(digits) != width or any(
            digit not in "0123456789abcdefABCDEF" for digit in digits
        ):
            raise ValueError("Displayed text contains an incomplete codepoint escape.")
        try:
            restored.append(chr(int(digits, 16)))
        except ValueError as error:
            raise ValueError(
                "Displayed text contains an invalid Unicode codepoint."
            ) from error
        index += 2 + width

    result = "".join(restored)
    if display_escape_text(result) != value:
        raise ValueError("Displayed text must use canonical terminal escapes.")
    return result
