"""Blank-line paragraph boundaries without interpreting Markdown punctuation."""

import re

from memcommit.models.corresponding_document_metadata import (
    CorrespondingDocumentMetadata,
)

from ..model import Document, DocumentBlock
from ..spacing import SpacingPolicy
from .markdown import render_markdown


def parse_text(text: str, *, path="document.txt", state=None) -> Document:
    if state is not None and state.path_scope == "PROFILE":
        return Document(
            state,
            (DocumentBlock("text", text, end_byte=len(text.encode("utf-8"))),)
            if text
            else (),
        )
    blocks = []
    start = 0
    for separator in (
        *re.finditer(r"(?:\r?\n)[ \t]*(?:\r?\n)(?:[ \t]*\r?\n)*", text),
        None,
    ):
        end = separator.start() if separator is not None else len(text)
        if start != end:
            blocks.append(
                DocumentBlock(
                    "text",
                    text[start:end],
                    start_byte=len(text[:start].encode("utf-8")),
                    end_byte=len(text[:end].encode("utf-8")),
                )
            )
        start = separator.end() if separator is not None else end
    return Document(state or CorrespondingDocumentMetadata(path, "txt"), tuple(blocks))


def render_text(
    document: Document, policy=SpacingPolicy(), *, source_ranges=None
) -> str:
    return render_markdown(document, policy, source_ranges=source_ranges)
