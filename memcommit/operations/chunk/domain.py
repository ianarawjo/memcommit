"""Operation-owned chunking methods for splitting Memory content.

Public API compatibility remains available through :mod:`memcommit.chunking`.

    chunks = chunk_content("some long text", "paragraphs")
    chunks = chunk_content(content, ChunkMethod.markdown_headers)
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Callable


_SENTENCE_DELIMITERS = frozenset(".!?。！？")
_CLAUSE_DELIMITERS = _SENTENCE_DELIMITERS | frozenset(";:—；：")
_CLOSING_PUNCTUATION = frozenset("\"'’”»)]}」』】")


def _split_at_boundaries(content: str, boundaries: list[int]) -> list[str]:
    chunks: list[str] = []
    start = 0
    for end in sorted(set(boundaries)):
        if end <= start or end >= len(content):
            continue
        chunk = content[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end
    final = content[start:].strip()
    if final:
        chunks.append(final)
    return chunks


def _markdown_header_boundaries(content: str) -> list[int]:
    headers: list[tuple[int, int]] = []
    offset = 0
    for line in content.splitlines(keepends=True):
        match = re.match(r"^(#{1,6}) ", line)
        if match:
            headers.append((offset, len(match.group(1))))
        offset += len(line)

    level_counts: dict[int, int] = {}
    for _offset, level in headers:
        level_counts[level] = level_counts.get(level, 0) + 1
    split_level = next(
        (level for level in sorted(level_counts) if level_counts[level] > 1),
        None,
    )
    if split_level is None:
        return []
    return [offset for offset, level in headers if level == split_level]


def _punctuation_boundaries(
    content: str,
    delimiters: frozenset[str],
    *,
    require_following_whitespace: bool,
) -> list[int]:
    """Return offsets after complete delimiter/closing-punctuation runs."""

    boundaries: list[int] = []
    index = 0
    while index < len(content):
        if content[index] not in delimiters:
            index += 1
            continue
        end = index + 1
        while end < len(content) and content[end] in delimiters:
            end += 1
        while end < len(content) and content[end] in _CLOSING_PUNCTUATION:
            end += 1
        if (
            not require_following_whitespace
            or end == len(content)
            or content[end].isspace()
        ):
            boundaries.append(end)
        index = end
    return boundaries


# ---------------------------------------------------------------------------
# Method implementations
# ---------------------------------------------------------------------------

def _by_markdown_headers(content: str) -> list[str]:
    """
    Split on the shallowest markdown header depth that appears more than once.

    The heuristic picks the smallest ``#``-level (1–6) that repeats — that
    level is almost always the natural "section boundary" of the document.
    Content before the first matching header (a preamble) is returned as its
    own chunk when non-empty.  Sub-headers below the split level are kept
    intact inside their parent chunk.

    Returns the original content as a single-element list when no repeating
    header depth is found (cannot split further).
    """
    return _split_at_boundaries(content, _markdown_header_boundaries(content))


def _by_paragraphs(content: str) -> list[str]:
    """Split on one or more blank lines (double-newline boundaries)."""
    chunks = re.split(r'\n[ \t]*\n', content)
    return [c.strip() for c in chunks if c.strip()]


def _by_sentences(content: str) -> list[str]:
    """
    Split on sentence boundaries (approximate heuristic).

    Splits after ``.``, ``!``, or ``?`` (and an optional closing quote) when
    followed by whitespace.  This deliberately does not require an uppercase
    next character: sentence chunking is also the CLI default for scripts and
    languages without Latin case.  It remains an approximate mechanical
    boundary and is less reliable on abbreviations or code snippets.
    """
    return _split_at_boundaries(
        content,
        _punctuation_boundaries(
            content,
            _SENTENCE_DELIMITERS,
            require_following_whitespace=True,
        ),
    )


def _by_clauses(content: str) -> list[str]:
    """Split after strong clause punctuation, retaining the punctuation."""

    return _split_at_boundaries(
        content,
        _punctuation_boundaries(
            content,
            _CLAUSE_DELIMITERS,
            require_following_whitespace=True,
        ),
    )


# ---------------------------------------------------------------------------
# Registry & public API
# ---------------------------------------------------------------------------

class ChunkMethod(str, Enum):
    """Named chunking strategies available to ``mem chunk``."""
    markdown_headers = "markdown_headers"
    paragraphs = "paragraphs"
    sentences = "sentences"
    clauses = "clauses"


_DISPATCH: dict[str, Callable[[str], list[str]]] = {
    "markdown_headers": _by_markdown_headers,
    "paragraphs":       _by_paragraphs,
    "sentences":        _by_sentences,
    "clauses":          _by_clauses,
}

#: Ordered list of valid method names (matches ChunkMethod enum values).
CHUNKING_METHODS: list[str] = [m.value for m in ChunkMethod]


def _validate_break_on(break_on: str | None) -> frozenset[str]:
    if break_on is None:
        return frozenset()
    if not isinstance(break_on, str) or not break_on:
        raise ValueError("break_on must contain at least one literal character.")
    if any(character.isspace() or character.isalnum() for character in break_on):
        raise ValueError(
            "break_on accepts literal punctuation or symbol characters only; "
            "whitespace and letters or digits are not valid boundaries."
        )
    return frozenset(break_on)


def _validate_char_limit(value: int | None, name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer.")


def _trim_span(content: str, start: int, end: int) -> tuple[int, int] | None:
    while start < end and content[start].isspace():
        start += 1
    while end > start and content[end - 1].isspace():
        end -= 1
    return (start, end) if start < end else None


def _spans_from_boundaries(content: str, boundaries: list[int]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    for end in sorted(set(boundaries)):
        if end <= start or end >= len(content):
            continue
        span = _trim_span(content, start, end)
        if span is not None:
            spans.append(span)
        start = end
    span = _trim_span(content, start, len(content))
    if span is not None:
        spans.append(span)
    return spans


def _split_oversized_span(
    content: str,
    span: tuple[int, int],
    max_chars: int,
) -> list[tuple[int, int]]:
    start, end = span
    pieces: list[tuple[int, int]] = []
    while end - start > max_chars:
        limit = start + max_chars
        cut = limit
        # Prefer the last whitespace inside the allowed window. If one long
        # token exceeds the hard limit, the explicit max still wins.
        for candidate in range(limit, start, -1):
            if content[candidate].isspace():
                cut = candidate
                break
        if cut <= start:
            cut = limit
        piece = _trim_span(content, start, cut)
        if piece is not None:
            pieces.append(piece)
        start = cut
        while start < end and content[start].isspace():
            start += 1
    final = _trim_span(content, start, end)
    if final is not None:
        pieces.append(final)
    return pieces


def _span_length(content: str, span: tuple[int, int]) -> int:
    return len(content[span[0] : span[1]].strip())


def _pack_spans(
    content: str,
    spans: list[tuple[int, int]],
    *,
    min_chars: int | None,
    max_chars: int | None,
) -> list[tuple[int, int]]:
    if not spans or (min_chars is None and max_chars is None):
        return spans

    if max_chars is not None:
        expanded: list[tuple[int, int]] = []
        for span in spans:
            expanded.extend(_split_oversized_span(content, span, max_chars))
        spans = expanded

        packed: list[tuple[int, int]] = []
        current = spans[0]
        for following in spans[1:]:
            combined = (current[0], following[1])
            if _span_length(content, combined) <= max_chars:
                current = combined
            else:
                packed.append(current)
                current = following
        packed.append(current)
    else:
        packed = []
        current = spans[0]
        for following in spans[1:]:
            if min_chars is not None and _span_length(content, current) >= min_chars:
                packed.append(current)
                current = following
            else:
                current = (current[0], following[1])
        packed.append(current)

    if min_chars is None or len(packed) <= 1:
        return packed

    # min_chars is a preferred floor: merge a short edge/interior piece when
    # doing so respects max_chars, but retain an unavoidable remainder rather
    # than crossing the explicit hard maximum or dropping content.
    index = 0
    while index < len(packed) and len(packed) > 1:
        if _span_length(content, packed[index]) >= min_chars:
            index += 1
            continue
        if index + 1 < len(packed):
            combined = (packed[index][0], packed[index + 1][1])
            if max_chars is None or _span_length(content, combined) <= max_chars:
                packed[index : index + 2] = [combined]
                continue
        if index > 0:
            combined = (packed[index - 1][0], packed[index][1])
            if max_chars is None or _span_length(content, combined) <= max_chars:
                packed[index - 1 : index + 1] = [combined]
                index -= 1
                continue
        index += 1
    return packed


def chunk_content(
    content: str,
    method: str | ChunkMethod,
    *,
    break_on: str | None = None,
    min_chars: int | None = None,
    max_chars: int | None = None,
) -> list[str]:
    """
    Split *content* into a list of non-empty stripped strings.

    *method* is either a :class:`ChunkMethod` enum value or its string name.
    ``break_on`` adds literal punctuation or symbol boundaries to the method.
    Character limits count Unicode code points after edge whitespace is
    stripped. ``max_chars`` is hard; ``min_chars`` is a preferred floor and
    can be missed only when merging would exceed the hard maximum.

    Raises :exc:`ValueError` for invalid methods, delimiters, or limits.
    """
    key = method.value if isinstance(method, ChunkMethod) else method
    fn = _DISPATCH.get(key)
    if fn is None:
        valid = ", ".join(CHUNKING_METHODS)
        raise ValueError(f"Unknown chunking method '{key}'. Valid: {valid}")
    delimiters = _validate_break_on(break_on)
    _validate_char_limit(min_chars, "min_chars")
    _validate_char_limit(max_chars, "max_chars")
    if min_chars is not None and max_chars is not None and min_chars > max_chars:
        raise ValueError("min_chars cannot be greater than max_chars.")

    if key == "markdown_headers":
        boundaries = _markdown_header_boundaries(content)
    elif key == "paragraphs":
        boundaries = [match.start() for match in re.finditer(r"\n[ \t]*\n", content)]
    elif key == "sentences":
        boundaries = _punctuation_boundaries(
            content,
            _SENTENCE_DELIMITERS,
            require_following_whitespace=True,
        )
    else:
        boundaries = _punctuation_boundaries(
            content,
            _CLAUSE_DELIMITERS,
            require_following_whitespace=True,
        )
    if delimiters:
        boundaries.extend(
            _punctuation_boundaries(
                content,
                delimiters,
                require_following_whitespace=False,
            )
        )

    spans = _spans_from_boundaries(content, boundaries)
    packed = _pack_spans(
        content,
        spans,
        min_chars=min_chars,
        max_chars=max_chars,
    )
    return [content[start:end].strip() for start, end in packed]
