"""Shared terminal rendering for read-only semantic finding commands."""
from __future__ import annotations

from collections.abc import Iterable

import typer

from memcommit.context import Memory
from memcommit.interfaces.console.text import display_escape_text
from memcommit.interfaces.console.theme import (
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
    memory_count: int,
    pair_count: int | None = None,
) -> None:
    """Render operation, target, and frozen scan scope as one report header."""
    typer.secho(operation_label, bold=True, nl=False)
    parts = [
        context_name,
        plural(memory_count, "direct memory", "direct memories") + " checked",
    ]
    if pair_count is not None:
        parts.append(plural(pair_count, "pair") + " checked")
    typer.echo(" · " + " · ".join(parts))


def render_finding_outcome(
    *,
    finding_count: int,
    singular: str,
    plural_form: str,
    empty_message: str,
) -> None:
    """Give the report conclusion its own line without repeating zero counts."""
    typer.echo()
    message = (
        empty_message
        if finding_count == 0
        else plural(finding_count, singular, plural_form)
    )
    typer.secho(message, bold=True)


def render_memory(label: str, memory: Memory) -> None:
    """Render a Memory without abbreviating its content."""
    typer.secho(f"  {label:<6} [{memory.uid[:8]}]", bold=True)
    for line in memory.content.splitlines() or [""]:
        typer.echo(f"         {line}")


def render_reason(reason: str) -> None:
    """Render model rationale as data, not as trusted terminal markup."""
    typer.secho(f"  Reason: {reason}", dim=True)


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
        typer.secho(f"  Question: {question}", fg=typer.colors.CYAN)


def render_values(label: str, values: Iterable[str]) -> None:
    """Render zero or more short structured values on one line."""
    materialized = list(values)
    if materialized:
        typer.echo(f"  {label}: {', '.join(materialized)}")
