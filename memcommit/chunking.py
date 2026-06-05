"""
Chunking methods for splitting Memory content into multiple pieces.

Public API:
    from memcommit.chunking import chunk_content, CHUNKING_METHODS, ChunkMethod

    chunks = chunk_content("some long text", "paragraphs")
    chunks = chunk_content(content, ChunkMethod.markdown_headers)
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Callable


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
    lines = content.splitlines(keepends=True)

    # Count occurrences of each header depth.
    level_counts: dict[int, int] = {}
    for line in lines:
        m = re.match(r'^(#{1,6}) ', line)
        if m:
            level = len(m.group(1))
            level_counts[level] = level_counts.get(level, 0) + 1

    # Smallest depth that appears more than once is the split boundary.
    split_level: int | None = None
    for level in sorted(level_counts):
        if level_counts[level] > 1:
            split_level = level
            break

    if split_level is None:
        stripped = content.strip()
        return [stripped] if stripped else []

    # '#' * split_level + ' ' is the exact prefix for that header depth.
    # Note: '## foo'.startswith('# ') is False, so deeper headers are safe.
    split_prefix = '#' * split_level + ' '

    chunks: list[str] = []
    current: list[str] = []

    for line in lines:
        if line.startswith(split_prefix) and current:
            chunk = ''.join(current).strip()
            if chunk:
                chunks.append(chunk)
            current = [line]
        else:
            current.append(line)

    if current:
        chunk = ''.join(current).strip()
        if chunk:
            chunks.append(chunk)

    return chunks


def _by_paragraphs(content: str) -> list[str]:
    """Split on one or more blank lines (double-newline boundaries)."""
    chunks = re.split(r'\n[ \t]*\n', content)
    return [c.strip() for c in chunks if c.strip()]


def _by_sentences(content: str) -> list[str]:
    """
    Split on sentence boundaries (approximate heuristic).

    Splits after ``.``, ``!``, or ``?`` when followed by whitespace and an
    uppercase letter or a closing quote.  Works well for ordinary prose; less
    reliable on technical text with abbreviations or code snippets.
    """
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z"‘’“”])', content)
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# Registry & public API
# ---------------------------------------------------------------------------

class ChunkMethod(str, Enum):
    """Named chunking strategies available to ``mem chunk``."""
    markdown_headers = "markdown_headers"
    paragraphs = "paragraphs"
    sentences = "sentences"


_DISPATCH: dict[str, Callable[[str], list[str]]] = {
    "markdown_headers": _by_markdown_headers,
    "paragraphs":       _by_paragraphs,
    "sentences":        _by_sentences,
}

#: Ordered list of valid method names (matches ChunkMethod enum values).
CHUNKING_METHODS: list[str] = [m.value for m in ChunkMethod]


def chunk_content(content: str, method: str | ChunkMethod) -> list[str]:
    """
    Split *content* into a list of non-empty stripped strings.

    *method* is either a :class:`ChunkMethod` enum value or its string name.
    Raises :exc:`ValueError` for unknown method names.
    """
    key = method.value if isinstance(method, ChunkMethod) else method
    fn = _DISPATCH.get(key)
    if fn is None:
        valid = ", ".join(CHUNKING_METHODS)
        raise ValueError(f"Unknown chunking method '{key}'. Valid: {valid}")
    return fn(content)
