"""Trusted terminal rendering for provisional atomize impact reports."""
from __future__ import annotations

import typer

from memcommit.atomize import AtomizeImpactReport, AtomizeItem


_CLASSIFICATION_COLORS = {
    "ATOMIC": typer.colors.GREEN,
    "COMPOSITE": typer.colors.YELLOW,
    "UNCERTAIN": typer.colors.RED,
    "NON_PROPOSITIONAL": typer.colors.CYAN,
}


def _render_source(item: AtomizeItem) -> None:
    for line in item.memory.content.splitlines() or [""]:
        if item.classification == "COMPOSITE":
            typer.secho(f"       - {line}", fg=typer.colors.RED)
        else:
            typer.echo(f"         {line}")


def _render_children(item: AtomizeItem) -> None:
    for index, child in enumerate(item.children, start=1):
        lines = child.content.splitlines() or [""]
        typer.secho(
            f"       + {index}. {lines[0]}",
            fg=typer.colors.GREEN,
        )
        for line in lines[1:]:
            typer.secho(f"            {line}", fg=typer.colors.GREEN)
        typer.secho(
            "         Cited source spans: "
            + " | ".join(child.source_spans),
            dim=True,
        )


def _render_item(item: AtomizeItem) -> None:
    color = _CLASSIFICATION_COLORS[item.classification]
    typer.echo()
    typer.secho(
        f"  {item.action:<15} {item.classification:<18} "
        f"[{item.memory.uid[:8]}]",
        fg=color,
        bold=True,
    )
    _render_source(item)
    if item.children:
        _render_children(item)
        typer.secho(
            "         Status: PROPOSED — independent validation is required "
            "before application.",
            dim=True,
        )
    typer.secho(
        f"         Rules: {', '.join(item.reason_codes)}",
        dim=True,
    )
    if item.lint:
        typer.secho(
            f"         Lint: {', '.join(item.lint)}",
            dim=True,
        )
    typer.secho(f"         Reason: {item.reason}", dim=True)


def render_atomize_impact(
    report: AtomizeImpactReport,
    *,
    show_all: bool,
) -> None:
    """Render canonical Context-ordered atomize proposals."""
    counts = {
        classification: report.count(classification)
        for classification in (
            "ATOMIC",
            "COMPOSITE",
            "UNCERTAIN",
            "NON_PROPOSITIONAL",
        )
    }
    child_count = sum(
        len(item.children)
        for item in report.items
        if item.classification == "COMPOSITE"
    )

    typer.secho(
        f"Atomize impact: {report.context_name}",
        bold=True,
    )
    typer.echo(
        f"  {report.memory_count} direct "
        f"{'Memory' if report.memory_count == 1 else 'Memories'} "
        f"-> {report.projected_memory_count} projected"
    )
    typer.echo(
        "  "
        f"{counts['ATOMIC']} atomic, "
        f"{counts['COMPOSITE']} composite, "
        f"{counts['UNCERTAIN']} uncertain, "
        f"{counts['NON_PROPOSITIONAL']} non-propositional"
    )
    typer.echo(
        f"  {counts['COMPOSITE']} proposed "
        f"{'split' if counts['COMPOSITE'] == 1 else 'splits'} "
        f"-> {child_count} children"
    )

    visible = [
        item
        for item in report.items
        if show_all or item.classification != "ATOMIC"
    ]
    if not visible:
        typer.echo("\n  (no atomization changes or review findings)")
    for item in visible:
        _render_item(item)

    if not show_all and counts["ATOMIC"]:
        typer.echo()
        typer.secho(
            f"  ({counts['ATOMIC']} atomic "
            f"{'Memory' if counts['ATOMIC'] == 1 else 'Memories'} hidden; "
            "use --all to show them)",
            dim=True,
        )

    typer.echo()
    typer.echo("No changes applied. No checkpoint created.")
