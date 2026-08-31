"""Operation-owned deterministic text Find application."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Protocol

from memcommit.application.capabilities.durable_uid_resolution import (
    DurableUidAmbiguityError,
    DurableUidCandidate,
    try_resolve_durable_uid,
)


FindMode = Literal["LITERAL", "REGEX"]
FindItemKind = Literal["memory", "memory_ref"]
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
    follow_embeds: bool = False
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
        if (
            type(self.include_descendants) is not bool
            or type(self.follow_embeds) is not bool
        ):
            raise FindInputError("Find reach choices must be booleans.")
        if self.mode not in {"LITERAL", "REGEX"}:
            raise FindInputError("Find mode must be LITERAL or REGEX.")
        if type(self.ignore_case) is not bool:
            raise FindInputError("Find ignore_case must be a boolean.")


@dataclass(frozen=True, slots=True)
class FindSourceItem:
    """One authorized Memory-shaped value frozen before matching."""

    context_name: str
    context_uid: str
    kind: FindItemKind
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
            raise FindError("Find source identities must be nonblank text.")
        if self.kind not in {"memory", "memory_ref"}:
            raise FindError("Find received an unsupported source item.")
        if (
            not isinstance(self.source_position, int)
            or isinstance(self.source_position, bool)
            or self.source_position < 1
        ):
            raise FindError("Find source position must be a positive integer.")
        if not isinstance(self.content, str):
            raise FindError("Find source content must be text.")
        reference = (
            self.source_context_name,
            self.source_context_uid,
            self.source_memory_uid,
        )
        if self.kind == "memory_ref":
            if not all(isinstance(value, str) and value for value in reference):
                raise FindError("Find Memory reference provenance must be complete.")
        elif any(value is not None for value in reference):
            raise FindError(
                "Direct Find Memory sources cannot carry reference provenance."
            )


@dataclass(frozen=True, slots=True)
class FrozenFindSource:
    """Complete authorized item frame for one request."""

    items: tuple[FindSourceItem, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.items, tuple) or any(
            not isinstance(item, FindSourceItem) for item in self.items
        ):
            raise FindError("Find source frame must contain typed items.")
        if tuple(item.source_position for item in self.items) != tuple(
            range(1, len(self.items) + 1)
        ):
            # The alias is a location in this complete frozen searchable frame,
            # not a rank among the later matching subset.
            raise FindError(
                "Find source positions must cover the frozen frame in order."
            )


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


@dataclass(frozen=True, slots=True)
class FindMatch:
    """Content occurrences and/or one durable identity match in a source item."""

    source: FindSourceItem
    spans: tuple[FindSpan, ...]
    matched_uids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.spans and not self.matched_uids:
            raise FindError("A Find match requires content or UID evidence.")
        if (
            not isinstance(self.matched_uids, tuple)
            or any(not isinstance(uid, str) or not uid for uid in self.matched_uids)
            or len(set(self.matched_uids)) != len(self.matched_uids)
        ):
            raise FindError("Find UID matches must contain distinct identities.")
        previous_end = -1
        for span in self.spans:
            if (
                span.start < previous_end
                or self.source.content[span.start : span.end] != span.text
            ):
                raise FindError("Find spans do not match the frozen content.")
            previous_end = span.end


@dataclass(frozen=True, slots=True)
class FindResult:
    """Complete provider-free result for the exact request."""

    request: FindRequest
    scanned_item_count: int
    matches: tuple[FindMatch, ...]

    @property
    def occurrence_count(self) -> int:
        return sum(len(match.spans) for match in self.matches)

    @property
    def identity_match_count(self) -> int:
        return sum(len(match.matched_uids) for match in self.matches)


class FindSourcePort(Protocol):
    def freeze(self, request: FindRequest) -> FrozenFindSource:
        """Return one complete authorized frame without constructing a provider."""


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


def run_find(
    request: FindRequest,
    *,
    source_port: FindSourcePort,
) -> FindResult:
    """Find every non-overlapping occurrence without provider or Store effects."""

    if not isinstance(request, FindRequest):
        raise FindInputError("Find requires a FindRequest.")
    compiled = compile_find_pattern(request)
    frozen = source_port.freeze(request)
    if not isinstance(frozen, FrozenFindSource):
        raise FindError("Find source returned an invalid frozen frame.")
    identity_by_position: dict[int, tuple[str, ...]] = {}
    if request.mode == "LITERAL":
        identity_candidates: list[DurableUidCandidate[FindSourceItem]] = []
        for item in frozen.items:
            identity_uids = [item.item_uid]
            if (
                item.source_memory_uid is not None
                and item.source_memory_uid != item.item_uid
            ):
                # Reference rows expose both the relationship and Source
                # Memory identities; either printed UID must round-trip.
                identity_uids.append(item.source_memory_uid)
            identity_candidates.extend(
                DurableUidCandidate(uid=uid, kind=item.kind, value=item)
                for uid in identity_uids
            )
        try:
            identity = try_resolve_durable_uid(
                tuple(identity_candidates),
                request.pattern,
            )
        except DurableUidAmbiguityError as error:
            raise FindInputError(str(error)) from error
        if identity is not None:
            for item in identity.values:
                identity_by_position[item.source_position] = (identity.uid,)
    matches: list[FindMatch] = []
    for item in frozen.items:
        spans = tuple(
            FindSpan(
                start=match.start(),
                end=match.end(),
                text=match.group(0),
            )
            for match in compiled.finditer(item.content)
        )
        matched_uids = identity_by_position.get(item.source_position, ())
        if spans or matched_uids:
            matches.append(
                FindMatch(
                    source=item,
                    spans=spans,
                    matched_uids=matched_uids,
                )
            )
    return FindResult(
        request=request,
        scanned_item_count=len(frozen.items),
        matches=tuple(matches),
    )


__all__ = [
    "FrozenFindSource",
    "FindError",
    "FindInputError",
    "FindItemKind",
    "FindMatch",
    "FindMode",
    "FindRequest",
    "FindResult",
    "FindSourceItem",
    "FindSourcePort",
    "FindSpan",
    "compile_find_pattern",
    "run_find",
]
