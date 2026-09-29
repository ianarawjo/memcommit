"""Compact applied receipt projection for Forget."""

from __future__ import annotations

import os
from typing import Sequence

import click
import typer

from memcommit.adapters.console.terminal.components.inline_diff import inline_diff_text
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.adapters.console.terminal.core.theme import (
    SemanticColorRole,
    semantic_color_rgb,
)
from memcommit.application.capabilities.semantic.changes import EditChange, ProposedChange, RemoveChange


def _colors_enabled() -> bool:
    """Match Click's output capability decision before choosing a text fallback."""

    if "NO_COLOR" in os.environ:
        return False
    context = click.get_current_context(silent=True)
    forced = context.color if context is not None else None
    stream = click.get_text_stream("stdout")
    return not click.utils.should_strip_ansi(stream, color=forced)


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
        return f"{marker} [{uid}] " + inline_diff_text(
            change.old_content, change.new_content, color=color
        )
    raise ValueError("Forget receipts may contain only removals and edits.")


def render_forget_change_lines(changes: Sequence[ProposedChange]) -> None:
    """Print each applied Forget change on exactly one logical output line."""

    color = _colors_enabled()
    for change in changes:
        typer.echo(_forget_change_line(change, color=color), color=color)


__all__ = [
    "render_forget_change_lines",
]
