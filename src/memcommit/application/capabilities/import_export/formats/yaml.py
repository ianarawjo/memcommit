"""Validate YAML syntax without constructing objects or reserializing values."""

from __future__ import annotations

import yaml

from ..model import Document, DocumentBlock, fail
from memcommit.core.document import DocumentState


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
            blocks.append(DocumentBlock("yaml", text[start:end]))
            start = end
    if start < len(text):
        blocks.append(DocumentBlock("yaml", text[start:]))
    return Document(state or DocumentState(path, "yaml"), tuple(blocks))


def render_yaml(document: Document) -> str:
    text = "".join(block.text for block in document.blocks)
    parse_yaml(text, path=document.state.path)
    protected = [
        (t.start_mark.index, t.end_mark.index)
        for t in yaml.scan(text, Loader=yaml.SafeLoader)
        if isinstance(t, yaml.tokens.ScalarToken)
    ]
    output = []
    offset = 0
    ordinary_blank = False
    for line in text.splitlines(keepends=True):
        end = offset + len(line)
        is_protected = any(start < end and stop > offset for start, stop in protected)
        blank = not line.strip() and not is_protected
        if not blank or not ordinary_blank:
            output.append(line)
        ordinary_blank = blank
        offset = end
    return "".join(output)
