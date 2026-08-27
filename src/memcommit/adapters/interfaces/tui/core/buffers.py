"""Unique prompt-toolkit buffer identities shared by components."""

from itertools import count


_BUFFER_SERIAL = count(1)


def next_buffer_name(kind: str) -> str:
    """Return an application-safe buffer name for one component family."""

    if not isinstance(kind, str) or not kind:
        raise ValueError("Buffer kind must be nonempty text.")
    return f"memcommit-{kind}-{next(_BUFFER_SERIAL)}"
