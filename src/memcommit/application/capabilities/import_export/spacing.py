"""Normalize only proven block separators; never strip a Memory's content."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SpacingPolicy:
    block_separator: str = "\n\n"
    list_separator: str = "\n"


def separator_between(previous, current, parent=None, policy=SpacingPolicy()) -> str:
    if parent == "tight_list":
        return policy.list_separator
    return policy.block_separator
