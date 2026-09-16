"""Retain source syntax; use CommonMark token ranges only to find block edges."""

from __future__ import annotations

import re
from markdown_it import MarkdownIt

from ..model import Document, DocumentBlock
from ..spacing import SpacingPolicy, separator_between
from memcommit.core.document import DocumentState


def parse_markdown(text: str, *, path="document.md", state=None) -> Document:
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
            return Document(
                body.state,
                (DocumentBlock("frontmatter", "".join(lines[: end + 1])),)
                + body.blocks,
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
        gap = _raw_gap(lines[cursor:start])
        if gap.strip():
            blocks.append(DocumentBlock("raw", gap))
        chunk = "".join(lines[start:end])
        # A parser range may include trailing separator lines after a list.
        # Protected blocks retain even trailing blank lines as content.
        if kind not in {"fence", "code_block", "html_block"}:
            chunk_lines = chunk.splitlines(keepends=True)
            while chunk_lines and not chunk_lines[-1].strip():
                chunk_lines.pop()
            chunk = "".join(chunk_lines)
        blocks.append(DocumentBlock(kind, chunk))
        cursor = end
    tail = _raw_gap(lines[cursor:])
    if tail.strip():
        blocks.append(DocumentBlock("raw", tail))
    return Document(state or DocumentState(path, "md"), tuple(blocks))


def _raw_gap(lines):
    lines = list(lines)
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "".join(lines)


def render_markdown(document: Document, policy=SpacingPolicy()) -> str:
    result = ""
    previous = None
    for block in document.blocks:
        if not block.text:
            continue
        if previous is not None:
            separator = separator_between(previous, block, policy=policy)
            # Add only missing separator newlines. Existing code/HTML content
            # must not be shortened to satisfy a cosmetic spacing preference.
            ending = re.search(r"(?:\r?\n)+$", result)
            trailing = ending.group().count("\n") if ending else 0
            result += separator[min(trailing, len(separator)) :]
        result += block.text
        previous = block
    return result


def normalized_markdown(text: str, policy=SpacingPolicy()) -> str:
    return render_markdown(parse_markdown(text), policy)
