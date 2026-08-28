"""Read UTF-8 text sources used by line-oriented console batches."""

from pathlib import Path
import sys


__all__ = ["read_batch_input_text"]


def read_batch_input_text(source: str) -> str:
    """Read *source* as UTF-8 text, treating ``-`` as standard input."""
    if source == "-":
        try:
            return sys.stdin.read()
        except OSError as error:
            raise ValueError(f"Could not read standard input: {error}") from error

    try:
        # Preserve physical line endings for provenance; command-owned parsers
        # still accept every line-ending form through str.splitlines().
        with Path(source).open(encoding="utf-8", newline="") as file:
            return file.read()
    except (OSError, UnicodeError) as error:
        raise ValueError(f"Could not read input '{source}': {error}") from error
