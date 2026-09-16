"""Blank-line paragraph boundaries without interpreting Markdown punctuation."""

import re

from ..model import Document, DocumentBlock
from ..spacing import SpacingPolicy
from .markdown import render_markdown
from memcommit.core.document import DocumentState


def parse_text(text: str, *, path="document.txt", state=None) -> Document:
    parts = re.split(r"(?:\r?\n)[ \t]*(?:\r?\n)(?:[ \t]*\r?\n)*", text)
    blocks = tuple(DocumentBlock("text", part) for part in parts if part)
    return Document(state or DocumentState(path, "txt"), blocks)


def render_text(document: Document, policy=SpacingPolicy()) -> str:
    return render_markdown(document, policy)
