"""Compact applied-receipt projection for Forget."""

from __future__ import annotations

import difflib
import os
import re
from dataclasses import dataclass
from typing import Literal, Sequence

import click
import typer

from memcommit.adapters.interfaces.console.text import display_escape_text
from memcommit.adapters.interfaces.console.theme import (
    SemanticColorRole,
    semantic_color_rgb,
)
from memcommit.application.semantic.changes import EditChange, ProposedChange, RemoveChange


_SpanKind = Literal["equal", "remove", "add"]


@dataclass(frozen=True)
class ForgetWordDiffSpan:
    """One mechanically classified span in an inline Forget edit."""

    kind: _SpanKind
    text: str


def _word_tokens(value: str) -> list[str]:
    return re.findall(r"\S+|\s+", value)


def forget_word_diff_spans(
    before: str,
    after: str,
) -> tuple[ForgetWordDiffSpan, ...]:
    """Interleave equal, removed, and added tokens without inferring meaning."""

    before_tokens = _word_tokens(display_escape_text(before))
    after_tokens = _word_tokens(display_escape_text(after))
    spans: list[ForgetWordDiffSpan] = []
    matcher = difflib.SequenceMatcher(
        None,
        before_tokens,
        after_tokens,
        autojunk=False,
    )
    for tag, before_start, before_end, after_start, after_end in matcher.get_opcodes():
        if tag in {"equal", "delete", "replace"}:
            before_text = "".join(before_tokens[before_start:before_end])
            if before_text:
                spans.append(
                    ForgetWordDiffSpan(
                        "equal" if tag == "equal" else "remove",
                        before_text,
                    )
                )
        if tag in {"insert", "replace"}:
            after_text = "".join(after_tokens[after_start:after_end])
            if after_text:
                spans.append(ForgetWordDiffSpan("add", after_text))

    merged: list[ForgetWordDiffSpan] = []
    for span in spans:
        if merged and merged[-1].kind == span.kind:
            previous = merged[-1]
            merged[-1] = ForgetWordDiffSpan(previous.kind, previous.text + span.text)
        else:
            merged.append(span)
    return tuple(merged)


def _colors_enabled() -> bool:
    """Match Click's output capability decision before choosing a text fallback."""

    if "NO_COLOR" in os.environ:
        return False
    context = click.get_current_context(silent=True)
    forced = context.color if context is not None else None
    stream = click.get_text_stream("stdout")
    return not click.utils.should_strip_ansi(stream, color=forced)


def _styled_span(span: ForgetWordDiffSpan) -> str:
    if span.kind == "equal":
        return span.text
    role = SemanticColorRole.REMOVE if span.kind == "remove" else SemanticColorRole.EDIT
    return typer.style(
        span.text,
        fg=semantic_color_rgb(role),
        underline=True,
    )


def _plain_span(span: ForgetWordDiffSpan) -> str:
    if span.kind == "equal":
        return span.text
    if span.kind == "remove":
        return f"[-{span.text}-]"
    return f"[+{span.text}+]"


def _forget_change_line(change: ProposedChange, *, color: bool) -> str:
    uid = change.uid[:8] if isinstance(change, (RemoveChange, EditChange)) else ""
    if isinstance(change, RemoveChange):
        marker = "-"
        content = display_escape_text(change.content)
        if color:
            marker = typer.style(
                marker,
                fg=semantic_color_rgb(SemanticColorRole.REMOVE),
                bold=True,
            )
            content = typer.style(
                content,
                fg=semantic_color_rgb(SemanticColorRole.REMOVE),
                underline=True,
            )
        return f"{marker} [{uid}] {content}"
    if isinstance(change, EditChange):
        marker = "~"
        if color:
            marker = typer.style(
                marker,
                fg=semantic_color_rgb(SemanticColorRole.EDIT),
                bold=True,
            )
        spans = forget_word_diff_spans(change.old_content, change.new_content)
        if color:
            rendered: list[str] = []
            for index, span in enumerate(spans):
                if (
                    index
                    and spans[index - 1].kind == "remove"
                    and span.kind == "add"
                    and not spans[index - 1].text[-1:].isspace()
                    and not span.text[:1].isspace()
                ):
                    rendered.append(" ")
                rendered.append(_styled_span(span))
        else:
            rendered = [_plain_span(span) for span in spans]
        return f"{marker} [{uid}] " + "".join(rendered)
    raise ValueError("Forget receipts may contain only removals and edits.")


def render_forget_change_lines(changes: Sequence[ProposedChange]) -> None:
    """Print each applied Forget change on exactly one logical output line."""

    color = _colors_enabled()
    for change in changes:
        typer.echo(_forget_change_line(change, color=color), color=color)


__all__ = [
    "ForgetWordDiffSpan",
    "forget_word_diff_spans",
    "render_forget_change_lines",
]
