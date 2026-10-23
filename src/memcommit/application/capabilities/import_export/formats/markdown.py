"""Retain source syntax; use CommonMark token ranges only to find block edges."""

from __future__ import annotations

import re
from dataclasses import replace

from markdown_it import MarkdownIt

from memcommit.models.corresponding_document_metadata import (
    CorrespondingDocumentMetadata,
)

from ..model import Document, DocumentBlock, DocumentSourceRange
from ..spacing import SpacingPolicy, separator_between


def parse_markdown(text: str, *, path="document.md", state=None) -> Document:
    lines = text.splitlines(keepends=True)
    line_byte_offsets = [0]
    for line in lines:
        line_byte_offsets.append(line_byte_offsets[-1] + len(line.encode("utf-8")))

    def block_from_lines(kind, lines, start, end):
        return DocumentBlock(
            kind,
            "".join(lines[start:end]),
            start_byte=line_byte_offsets[start],
            end_byte=line_byte_offsets[end],
        )

    def retained_gap(lines, start, end):
        while start < end and not lines[start].strip():
            start += 1
        while end > start and not lines[end - 1].strip():
            end -= 1
        return block_from_lines("raw", lines, start, end)

    if state is not None and state.path_scope == "PROFILE":
        # Project imports retain separators as ordinary Memory text so initial
        # Sync can adopt identical files without normalizing somebody's rules.
        tokens = MarkdownIt("commonmark").enable(["table", "strikethrough"]).parse(text)
        lines = text.splitlines(keepends=True)
        starts = sorted(
            {t.map[0] for t in tokens if t.level == 0 and t.map is not None}
        )
        boundaries = sorted({0, *starts, len(lines)})
        blocks = tuple(
            block_from_lines("raw", lines, a, z)
            for a, z in zip(boundaries, boundaries[1:])
            if a != z
        )
        return Document(state, blocks)
    lines = text.splitlines(keepends=True)
    # Frontmatter is a protected syntax block even outside a Skill package.
    if lines and lines[0].lstrip("\ufeff").rstrip("\r\n") == "---":
        end = next(
            (
                i
                for i in range(1, len(lines))
                if lines[i].rstrip("\r\n") in {"---", "..."}
            ),
            None,
        )
        if end is not None:
            body = parse_markdown("".join(lines[end + 1 :]), path=path, state=state)
            body_offset = len("".join(lines[: end + 1]).encode("utf-8"))
            return Document(
                body.state,
                (block_from_lines("frontmatter", lines, 0, end + 1),)
                + tuple(
                    replace(
                        block,
                        start_byte=block.start_byte + body_offset,
                        end_byte=block.end_byte + body_offset,
                    )
                    for block in body.blocks
                ),
            )
    tokens = MarkdownIt("commonmark").enable(["table", "strikethrough"]).parse(text)
    ranges = [
        (t.map[0], t.map[1], t.type)
        for t in tokens
        if t.level == 0 and t.map is not None and t.nesting >= 0
    ]
    # Reference definitions are absent from the token stream. Preserve every
    # uncovered nonblank line instead of reconstructing text from token.content.
    blocks = []
    cursor = 0
    for start, end, kind in ranges:
        if start < cursor:
            continue
        gap = retained_gap(lines, cursor, start)
        if gap.text.strip():
            blocks.append(gap)
        chunk = "".join(lines[start:end])
        # A parser range may include trailing separator lines after a list.
        # Protected blocks retain even trailing blank lines as content.
        if kind not in {"fence", "code_block", "html_block"}:
            chunk_lines = chunk.splitlines(keepends=True)
            while chunk_lines and not chunk_lines[-1].strip():
                chunk_lines.pop()
            chunk = "".join(chunk_lines)
        blocks.append(
            block_from_lines(
                kind, lines, start, start + len(chunk.splitlines(keepends=True))
            )
        )
        cursor = end
    tail = retained_gap(lines, cursor, len(lines))
    if tail.text.strip():
        blocks.append(tail)
    return Document(state or CorrespondingDocumentMetadata(path, "md"), tuple(blocks))


def _raw_gap(lines):
    lines = list(lines)
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "".join(lines)


def render_markdown(
    document: Document, policy=SpacingPolicy(), *, source_ranges=None
) -> str:
    result = ""
    previous = None
    for block in document.blocks:
        if not block.text:
            continue
        if previous is not None and document.state.path_scope != "PROFILE":
            separator = separator_between(previous, block, policy=policy)
            # Add only missing separator newlines. Existing code/HTML content
            # must not be shortened to satisfy a cosmetic spacing preference.
            ending = re.search(r"(?:\r?\n)+$", result)
            trailing = ending.group().count("\n") if ending else 0
            result += separator[min(trailing, len(separator)) :]
        start = len(result.encode("utf-8"))
        result += block.text
        if source_ranges is not None and block.source is not None:
            source_ranges.append(
                DocumentSourceRange(start, len(result.encode("utf-8")), block.source)
            )
        previous = block
    return result


def normalized_markdown(text: str, policy=SpacingPolicy()) -> str:
    return render_markdown(parse_markdown(text), policy)
