"""Parse Edit's line-oriented input records."""


__all__ = ["parse_input_records"]


def parse_input_records(text: str) -> list[tuple[str, str]]:
    """Parse non-empty ``UID<TAB>replacement content`` records."""
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
