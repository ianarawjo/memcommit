"""Option values and display text shared by console selection controls."""

from __future__ import annotations

from dataclasses import dataclass


def _is_nonempty_single_line(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and "\r" not in value
        and "\n" not in value
    )


@dataclass(frozen=True)
class SelectionOption:
    """One option's stable value and display text, independent of layout."""

    value: str
    label: str
    description: str = ""

    def __post_init__(self) -> None:
        if (
            not _is_nonempty_single_line(self.value)
            or not _is_nonempty_single_line(self.label)
            or not isinstance(self.description, str)
        ):
            raise ValueError("Selection options require stable text identity.")
