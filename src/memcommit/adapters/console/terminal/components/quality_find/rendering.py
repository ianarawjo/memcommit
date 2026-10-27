"""Shared terminal rendering for read-only quality-find commands."""

from __future__ import annotations

from collections.abc import Iterable

import typer

from memcommit.models.memory import Memory
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.adapters.console.terminal.components.inline_diff import (
    render_inline_memory_change_text,
)
from memcommit.application.capabilities.reviewing.memory_diff import MemoryChange


def plural(count: int, singular: str, plural_form: str | None = None) -> str:
    """Return a count with a naturally pluralized label."""
    label = singular if count == 1 else (plural_form or f"{singular}s")
    return f"{count} {label}"


def render_heading(
    *,
    operation_label: str,
    context_name: str,
    facts: Iterable[str],
) -> None:
    """Render operation, target, and exact result units as one report header."""
    typer.secho(operation_label, bold=True, nl=False)
    typer.echo(" · " + " · ".join((context_name, *facts)))


def render_memory(
    memory: Memory,
    *,
    uid_prefix: str,
    context_name: str | None = None,
) -> None:
    """Render one complete Memory reference as a single safe logical line."""
    heading = "  "
    if context_name is not None:
        heading += f"[CONTEXT {display_escape_text(context_name)}] "
    heading += f"[{display_escape_text(uid_prefix)}] "
    typer.echo(heading + display_escape_text(memory.content))


def render_reason(reason: str) -> None:
    """Render model rationale as data, not as trusted terminal markup."""
    typer.secho(f"  Reason: {display_escape_text(reason)}", dim=True)


def render_cleanup_memory_change(
    change: MemoryChange,
    *,
    uid_prefix: str,
) -> None:
    """Indent one proposed located diff while preserving unambiguous UID prefixes."""
    typer.echo(
        "    " + render_inline_memory_change_text(
            change,
            identity=f"[{change.location}:{uid_prefix}]",
            color=True,
        )
    )


def render_question(question: str | None) -> None:
    """Render the smallest proposed clarification when one was returned."""
    if question:
        typer.secho(
            f"  Question: {display_escape_text(question)}",
            fg=typer.colors.CYAN,
        )


def render_readings(values: Iterable[str]) -> None:
    """Render provider readings with boundaries that survive embedded commas."""
    materialized = list(values)
    for index, value in enumerate(materialized, start=1):
        label = "Reading" if len(materialized) == 1 else f"Reading {index}"
        typer.echo(f"  {label}: {display_escape_text(value)}")
