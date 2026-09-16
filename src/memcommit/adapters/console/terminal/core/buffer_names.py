"""Numbered default names for prompt-toolkit buffers."""

from itertools import count


_BUFFER_SERIAL = count(1)


def next_numbered_buffer_name(kind: str) -> str:
    """Append the next process-local serial to a component family's buffer name."""

    if not isinstance(kind, str) or not kind:
        raise ValueError("Buffer kind must be nonempty text.")
    return f"memcommit-{kind}-{next(_BUFFER_SERIAL)}"
