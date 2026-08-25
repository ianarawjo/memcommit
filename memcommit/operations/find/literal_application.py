"""Operation-owned deterministic text Find application."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Protocol


LiteralFindMode = Literal["LITERAL", "REGEX"]
LiteralFindItemKind = Literal["memory", "memory_ref"]
_PATTERN_LIMIT = 2_000


class LiteralFindError(RuntimeError):
    """Base failure for provider-free text Find."""


class LiteralFindInputError(LiteralFindError, ValueError):
    """The requested pattern or scope is invalid."""


@dataclass(frozen=True, slots=True)
class LiteralFindRequest:
    """One exact text pattern and readable Context scope."""

    pattern: str
    target_names: tuple[str, ...]
    include_descendants: bool = False
    follow_embeds: bool = False
    mode: LiteralFindMode = "LITERAL"
    ignore_case: bool = False

    def __post_init__(self) -> None:
        if (
            not isinstance(self.pattern, str)
            or not self.pattern
            or len(self.pattern) > _PATTERN_LIMIT
        ):
            raise LiteralFindInputError(
                f"Find pattern must contain 1–{_PATTERN_LIMIT:,} characters."
            )
        if (
            not isinstance(self.target_names, tuple)
            or not self.target_names
            or any(not isinstance(name, str) or not name for name in self.target_names)
            or len(set(self.target_names)) != len(self.target_names)
        ):
            raise LiteralFindInputError(
                "Find requires at least one distinct readable Context."
            )
        if type(self.include_descendants) is not bool or type(
            self.follow_embeds
        ) is not bool:
            raise LiteralFindInputError("Find reach choices must be booleans.")
        if self.mode not in {"LITERAL", "REGEX"}:
            raise LiteralFindInputError("Find mode must be LITERAL or REGEX.")
        if type(self.ignore_case) is not bool:
            raise LiteralFindInputError("Find ignore_case must be a boolean.")


@dataclass(frozen=True, slots=True)
class LiteralFindSourceItem:
    """One authorized Memory-shaped value frozen before matching."""

    context_name: str
    context_uid: str
    kind: LiteralFindItemKind
    item_uid: str
    source_position: int
    content: str
    source_context_name: str | None = None
    source_context_uid: str | None = None
    source_memory_uid: str | None = None

    def __post_init__(self) -> None:
        text_values = (
            self.context_name,
            self.context_uid,
            self.item_uid,
        )
        if any(not isinstance(value, str) or not value for value in text_values):
            raise LiteralFindError("Find source identities must be nonblank text.")
        if self.kind not in {"memory", "memory_ref"}:
            raise LiteralFindError("Find received an unsupported source item.")
        if (
            not isinstance(self.source_position, int)
            or isinstance(self.source_position, bool)
            or self.source_position < 1
        ):
            raise LiteralFindError(
                "Find source position must be a positive integer."
            )
        if not isinstance(self.content, str):
            raise LiteralFindError("Find source content must be text.")
        reference = (
            self.source_context_name,
            self.source_context_uid,
            self.source_memory_uid,
        )
        if self.kind == "memory_ref":
            if not all(isinstance(value, str) and value for value in reference):
                raise LiteralFindError(
                    "Find Memory reference provenance must be complete."
                )
        elif any(value is not None for value in reference):
            raise LiteralFindError(
                "Direct Find Memory sources cannot carry reference provenance."
            )


@dataclass(frozen=True, slots=True)
class FrozenLiteralFindSource:
    """Complete authorized item frame for one request."""

    items: tuple[LiteralFindSourceItem, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.items, tuple) or any(
            not isinstance(item, LiteralFindSourceItem) for item in self.items
        ):
            raise LiteralFindError("Find source frame must contain typed items.")
        if tuple(item.source_position for item in self.items) != tuple(
            range(1, len(self.items) + 1)
        ):
            # The alias is a location in this complete frozen searchable frame,
            # not a rank among the later matching subset.
            raise LiteralFindError(
                "Find source positions must cover the frozen frame in order."
            )


@dataclass(frozen=True, slots=True)
class LiteralFindSpan:
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
            raise LiteralFindError("Find returned an invalid text span.")


@dataclass(frozen=True, slots=True)
class LiteralFindMatch:
    """All non-overlapping matches in one frozen Memory-shaped item."""

    source: LiteralFindSourceItem
    spans: tuple[LiteralFindSpan, ...]

    def __post_init__(self) -> None:
        if not self.spans:
            raise LiteralFindError("A Find match requires at least one span.")
        previous_end = -1
        for span in self.spans:
            if span.start < previous_end or self.source.content[span.start : span.end] != span.text:
                raise LiteralFindError("Find spans do not match the frozen content.")
            previous_end = span.end


@dataclass(frozen=True, slots=True)
class LiteralFindResult:
    """Complete provider-free result for the exact request."""

    request: LiteralFindRequest
    scanned_item_count: int
    matches: tuple[LiteralFindMatch, ...]

    @property
    def occurrence_count(self) -> int:
        return sum(len(match.spans) for match in self.matches)


class LiteralFindSourcePort(Protocol):
    def freeze(self, request: LiteralFindRequest) -> FrozenLiteralFindSource:
        """Return one complete authorized frame without constructing a provider."""


def compile_find_pattern(request: LiteralFindRequest) -> re.Pattern[str]:
    """Compile literal or explicit regex matching under one bounded contract."""

    flags = re.IGNORECASE if request.ignore_case else 0
    pattern = re.escape(request.pattern) if request.mode == "LITERAL" else request.pattern
    try:
        compiled = re.compile(pattern, flags)
    except re.error as error:
        raise LiteralFindInputError(f"Invalid Find regular expression: {error}") from error
    if request.mode == "REGEX" and compiled.search("") is not None:
        # Zero-width matches are useful in a programming regex engine but are
        # not independently reviewable text occurrences and make replacement
        # cardinality surprising. Keep Find and the later Replace plan aligned.
        raise LiteralFindInputError(
            "Find regular expressions must consume at least one character."
        )
    return compiled


def run_literal_find(
    request: LiteralFindRequest,
    *,
    source_port: LiteralFindSourcePort,
) -> LiteralFindResult:
    """Find every non-overlapping occurrence without provider or Store effects."""

    if not isinstance(request, LiteralFindRequest):
        raise LiteralFindInputError("Find requires a LiteralFindRequest.")
    compiled = compile_find_pattern(request)
    frozen = source_port.freeze(request)
    if not isinstance(frozen, FrozenLiteralFindSource):
        raise LiteralFindError("Find source returned an invalid frozen frame.")
    matches: list[LiteralFindMatch] = []
    for item in frozen.items:
        spans = tuple(
            LiteralFindSpan(
                start=match.start(),
                end=match.end(),
                text=match.group(0),
            )
            for match in compiled.finditer(item.content)
        )
        if spans:
            matches.append(LiteralFindMatch(source=item, spans=spans))
    return LiteralFindResult(
        request=request,
        scanned_item_count=len(frozen.items),
        matches=tuple(matches),
    )


__all__ = [
    "FrozenLiteralFindSource",
    "LiteralFindError",
    "LiteralFindInputError",
    "LiteralFindItemKind",
    "LiteralFindMatch",
    "LiteralFindMode",
    "LiteralFindRequest",
    "LiteralFindResult",
    "LiteralFindSourceItem",
    "LiteralFindSourcePort",
    "LiteralFindSpan",
    "compile_find_pattern",
    "run_literal_find",
]
