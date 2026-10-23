"""Validate YAML syntax without constructing objects or reserializing values."""

from __future__ import annotations

from dataclasses import replace

import yaml

from memcommit.models.corresponding_document_metadata import (
    CorrespondingDocumentMetadata,
)

from ..model import Document, DocumentBlock, DocumentSourceRange, fail


def parse_yaml(text: str, *, path="document.yaml", state=None) -> Document:
    try:
        # Scanner positions protect block scalar whitespace. No constructors,
        # including custom tags, run while importing a document.
        tokens = list(yaml.scan(text, Loader=yaml.SafeLoader))
        list(yaml.parse(text, Loader=yaml.SafeLoader))
    except yaml.YAMLError as error:
        fail("invalid-yaml", path, str(error))
    blocks = []
    start = 0
    start_byte = 0

    def append_block(end):
        nonlocal start_byte
        content = text[start:end]
        end_byte = start_byte + len(content.encode("utf-8"))
        blocks.append(
            DocumentBlock(
                "yaml",
                content,
                start_byte=start_byte,
                end_byte=end_byte,
            )
        )
        start_byte = end_byte

    # Top-level keys provide editable syntax units, while retaining comments,
    # quotes and exact literal/folded scalar content in the Memory itself.
    starts = sorted(
        {
            t.start_mark.index
            for t in tokens
            if isinstance(t, yaml.tokens.KeyToken) and t.start_mark.column == 0
        }
    )
    for end in starts:
        if end > start and text[start:end].strip():
            append_block(end)
            start = end
    if start < len(text):
        append_block(len(text))
    return Document(state or CorrespondingDocumentMetadata(path, "yaml"), tuple(blocks))


def render_yaml(document: Document, *, source_ranges=None) -> str:
    text = "".join(block.text for block in document.blocks)
    parse_yaml(text, path=document.state.path)
    protected = [
        (t.start_mark.index, t.end_mark.index)
        for t in yaml.scan(text, Loader=yaml.SafeLoader)
        if isinstance(t, yaml.tokens.ScalarToken)
    ]
    output = []
    offset = 0
    input_byte_offset = output_byte_offset = 0
    owned_blocks = []
    for block in document.blocks:
        block_end = input_byte_offset + len(block.text.encode("utf-8"))
        if block.source is not None:
            owned_blocks.append((input_byte_offset, block_end, block.source))
        input_byte_offset = block_end
    input_byte_offset = 0
    owner_cursor = 0
    ordinary_blank = False
    for line in text.splitlines(keepends=True):
        end = offset + len(line)
        line_bytes = len(line.encode("utf-8"))
        is_protected = any(start < end and stop > offset for start, stop in protected)
        blank = not line.strip() and not is_protected
        if not blank or not ordinary_blank:
            output.append(line)
            if source_ranges is not None:
                while (
                    owner_cursor < len(owned_blocks)
                    and owned_blocks[owner_cursor][1] <= input_byte_offset
                ):
                    owner_cursor += 1
                candidate = owner_cursor
                while candidate < len(owned_blocks):
                    block_start, block_end, source = owned_blocks[candidate]
                    if block_start >= input_byte_offset + line_bytes:
                        break
                    candidate += 1
                    start = max(block_start, input_byte_offset)
                    stop = min(block_end, input_byte_offset + line_bytes)
                    if start >= stop:
                        continue
                    emitted = DocumentSourceRange(
                        output_byte_offset + start - input_byte_offset,
                        output_byte_offset + stop - input_byte_offset,
                        replace(
                            source,
                            start=source.start + start - block_start,
                            end=source.start + stop - block_start,
                        ),
                    )
                    _append_source_range(source_ranges, emitted)
            output_byte_offset += line_bytes
        ordinary_blank = blank
        offset = end
        input_byte_offset += line_bytes
    return "".join(output)


def _append_source_range(ranges, emitted):
    # Adjacent retained lines remain one reversible source run; normalization
    # must leave a source gap for every dropped cosmetic blank line.
    previous = ranges[-1] if ranges else None
    if (
        previous is not None
        and previous.end == emitted.start
        and previous.source.end == emitted.source.start
        and previous.source.context_uid == emitted.source.context_uid
        and previous.source.context_name == emitted.source.context_name
        and previous.source.memory_uid == emitted.source.memory_uid
    ):
        ranges[-1] = DocumentSourceRange(
            previous.start,
            emitted.end,
            replace(previous.source, end=emitted.source.end),
        )
    else:
        ranges.append(emitted)
