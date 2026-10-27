"""Retain source syntax; use CommonMark token ranges only to find block edges."""

from __future__ import annotations

import re
from dataclasses import replace

from markdown_it import MarkdownIt
from markdown_it.rules_block.state_block import StateBlock

from memcommit.models.corresponding_document_metadata import (
    CorrespondingDocumentMetadata,
)

from ..model import Document, DocumentBlock, DocumentSourceRange
from ..spacing import SpacingPolicy, separator_between


def _parse_footnote_definition(
    state: StateBlock, start_line: int, end_line: int, silent: bool
) -> bool:
    if state.is_code_block(start_line):
        return False
    start = state.bMarks[start_line] + state.tShift[start_line]
    first_line = state.src[start : state.eMarks[start_line]]
    if re.match(r"\[\^[^\]\r\n]+\]:", first_line) is None:
        return False
    if silent:
        return True

    definition_end = start_line + 1
    next_line = definition_end
    while next_line < end_line:
        if state.isEmpty(next_line):
            next_line += 1
            continue
        if state.sCount[next_line] - state.blkIndent < 4:
            break
        definition_end = next_line + 1
        next_line += 1

    # Retain source syntax rather than expanding footnotes into generated HTML.
    token = state.push("footnote_definition", "", 0)
    token.block = True
    token.map = [start_line, definition_end]
    state.line = definition_end
    return True


def _iter_memory_block_ranges(tokens):
    for index, token in enumerate(tokens):
        if token.level != 0 or token.map is None or token.nesting < 0:
            continue
        if token.type in {"bullet_list_open", "ordered_list_open"}:
            kind = (
                "bullet_list_item"
                if token.type == "bullet_list_open"
                else "ordered_list_item"
            )
            for child in tokens[index + 1 :]:
                if child.level == 0:
                    break
                if child.type == "list_item_open" and child.level == 1:
                    yield child.map[0], child.map[1], kind
        elif token.type == "paragraph_open":
            for line in range(*token.map):
                yield line, line + 1, token.type
        else:
            yield token.map[0], token.map[1], token.type


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

    # Keep the complete header in one Memory without interpreting its fields.
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
    parser = MarkdownIt("commonmark").enable(["table", "strikethrough"])
    parser.block.ruler.before(
        "reference",
        "footnote_definition",
        _parse_footnote_definition,
        {"alt": ["paragraph", "reference", "blockquote"]},
    )
    ranges = _iter_memory_block_ranges(parser.parse(text))
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
        if previous is not None:
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
