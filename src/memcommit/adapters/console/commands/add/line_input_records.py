"""Parse Add's line-input records."""


__all__ = ["parse_line_input_records"]


def parse_line_input_records(text: str) -> list[str]:
    """Return stripped, non-empty physical lines as Memory contents."""
    contents = []

    for line in text.splitlines():
        content = line.strip()

        if content:
            contents.append(content)

    if not contents:
        raise ValueError("Input contains no non-empty lines.")
    return contents
