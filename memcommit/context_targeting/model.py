"""Operation-neutral values describing Context targets and lexical reach."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal


ContextSelectionMode = Literal["SINGLE", "MULTIPLE"]


@dataclass(frozen=True)
class ContextScope:
    """One frozen set of Context names and its lexical descendant policy.

    Embedded-Context traversal is deliberately not part of this value.  It is
    a loading policy that some read operations expose independently, whereas
    lexical reach is shared by Find and saved-session operations.
    """

    target_names: tuple[str, ...]
    include_descendants: bool

    @classmethod
    def create(
        cls,
        target_names: Sequence[str],
        *,
        include_descendants: bool,
    ) -> "ContextScope":
        names = tuple(target_names)
        if (
            not names
            or len(set(names)) != len(names)
            or any(not isinstance(name, str) or not name for name in names)
        ):
            raise ValueError("Context scope requires distinct named targets.")
        if type(include_descendants) is not bool:
            raise ValueError("Context descendant scope must be a boolean.")
        return cls(names, include_descendants)
