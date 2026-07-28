"""Shared file/stdin loading for line-oriented structural commands."""

from pathlib import Path
import sys


def read_text_input(source: str) -> str:
    """Read UTF-8 text from *source*, where ``-`` means standard input."""
    if source == "-":
        try:
            return sys.stdin.read()
        except OSError as error:
            raise ValueError(f"Could not read standard input: {error}") from error

    try:
        return Path(source).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ValueError(f"Could not read input '{source}': {error}") from error


def parse_add_lines(text: str) -> list[str]:
    """Return stripped, non-empty physical lines as Memory contents."""
    contents = [line.strip() for line in text.splitlines() if line.strip()]
    if not contents:
        raise ValueError("Input contains no non-empty lines.")
    return contents


def parse_edit_lines(text: str) -> list[tuple[str, str]]:
    """
    Parse ``UID<TAB>replacement content`` records.

    Empty physical lines are ignored.  The selector is stripped, while the
    replacement after the first tab is preserved exactly.
    """
    edits: list[tuple[str, str]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        if "\t" not in line:
            raise ValueError(
                f"Line {line_number}: expected UID<TAB>replacement content."
            )
        selector, content = line.split("\t", 1)
        selector = selector.strip()
        if not selector:
            raise ValueError(f"Line {line_number}: Memory UID is empty.")
        edits.append((selector, content))

    if not edits:
        raise ValueError("Input contains no edit records.")
    return edits
