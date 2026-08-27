"""Shared terminal rendering for read-only semantic finding commands."""

from __future__ import annotations

from collections.abc import Iterable

import typer

from memcommit.core.context import Memory
from memcommit.adapters.console.text import display_escape_text
from memcommit.adapters.console.theme import (
    SemanticColorRole,
    semantic_color_rgb,
)


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


def render_cleanup_member(
    role: str,
    uid_prefix: str,
    *,
    content: str | None = None,
) -> None:
    """Render one proposed cleanup disposition using the shared action palette."""

    if role not in {"SURVIVOR", "ABSORB"}:
        raise ValueError("Cleanup members require SURVIVOR or ABSORB.")
    color_role = (
        SemanticColorRole.ADD if role == "SURVIVOR" else SemanticColorRole.REMOVE
    )
    typer.echo("    ", nl=False)
    typer.secho(
        role,
        fg=semantic_color_rgb(color_role),
        bold=True,
        nl=False,
    )
    suffix = f"  [memory {display_escape_text(uid_prefix)}]"
    if content is not None:
        suffix += "  " + display_escape_text(content)
    typer.echo(" " * (8 - len(role)) + suffix)


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
