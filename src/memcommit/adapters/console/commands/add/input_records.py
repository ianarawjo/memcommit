"""Parse Add's line-oriented input records."""


__all__ = ["parse_input_records"]


def parse_input_records(text: str) -> list[str]:
    """Return stripped, non-empty physical lines as Memory contents."""
    contents = [line.strip() for line in text.splitlines() if line.strip()]
    if not contents:
        raise ValueError("Input contains no non-empty lines.")
    return contents
