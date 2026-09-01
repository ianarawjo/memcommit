"""Application-owned parsing for line-oriented Add text."""

from __future__ import annotations


def parse_line_input_records(text: str) -> tuple[str, ...]:
    """Return stripped, non-empty physical lines as Memory contents."""

    if not isinstance(text, str):
        raise TypeError("Add line input must be text.")

    contents = tuple(content for line in text.splitlines() if (content := line.strip()))
    if not contents:
        raise ValueError("Input contains no non-empty lines.")
    return contents


__all__ = ["parse_line_input_records"]
