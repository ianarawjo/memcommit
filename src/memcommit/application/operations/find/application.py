"""Exact text-pattern contract that deterministic Replace matches against."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


FindMode = Literal["LITERAL", "REGEX"]
_PATTERN_LIMIT = 2_000


class FindError(RuntimeError):
    """Base failure for provider-free text Find."""


class FindInputError(FindError, ValueError):
    """The requested pattern or scope is invalid."""


@dataclass(frozen=True, slots=True)
class FindRequest:
    """One exact text pattern and readable Context scope."""

    pattern: str
    target_names: tuple[str, ...]
    include_descendants: bool = False
    mode: FindMode = "LITERAL"
    ignore_case: bool = False

    def __post_init__(self) -> None:
        if (
            not isinstance(self.pattern, str)
            or not self.pattern
            or len(self.pattern) > _PATTERN_LIMIT
        ):
            raise FindInputError(
                f"Find pattern must contain 1–{_PATTERN_LIMIT:,} characters."
            )
        if (
            not isinstance(self.target_names, tuple)
            or not self.target_names
            or any(not isinstance(name, str) or not name for name in self.target_names)
            or len(set(self.target_names)) != len(self.target_names)
        ):
            raise FindInputError(
                "Find requires at least one distinct readable Context."
            )
        if type(self.include_descendants) is not bool:
            raise FindInputError("Find reach choices must be booleans.")
        if self.mode not in {"LITERAL", "REGEX"}:
            raise FindInputError("Find mode must be LITERAL or REGEX.")
        if type(self.ignore_case) is not bool:
            raise FindInputError("Find ignore_case must be a boolean.")


@dataclass(frozen=True, slots=True)
class FindSpan:
    start: int
    end: int
    text: str

    def __post_init__(self) -> None:
        if (
            isinstance(self.start, bool)
            or isinstance(self.end, bool)
            or not isinstance(self.start, int)
            or not isinstance(self.end, int)
            or self.start < 0
            or self.end <= self.start
            or not isinstance(self.text, str)
            or len(self.text) != self.end - self.start
        ):
            raise FindError("Find returned an invalid text span.")


def compile_find_pattern(request: FindRequest) -> re.Pattern[str]:
    """Compile literal or explicit regex matching under one bounded contract."""

    flags = re.IGNORECASE if request.ignore_case else 0
    pattern = (
        re.escape(request.pattern) if request.mode == "LITERAL" else request.pattern
    )
    try:
        compiled = re.compile(pattern, flags)
    except re.error as error:
        raise FindInputError(f"Invalid Find regular expression: {error}") from error
    if request.mode == "REGEX" and compiled.search("") is not None:
        # Zero-width matches are useful in a programming regex engine but are
        # not independently reviewable text occurrences and make replacement
        # cardinality surprising. Keep Find and the later Replace plan aligned.
        raise FindInputError(
            "Find regular expressions must consume at least one character."
        )
    return compiled


__all__ = [
    "FindError",
    "FindInputError",
    "FindMode",
    "FindRequest",
    "FindSpan",
    "compile_find_pattern",
]
