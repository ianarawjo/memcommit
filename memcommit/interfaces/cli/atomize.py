"""Trusted terminal rendering for provisional atomize impact reports."""

from __future__ import annotations

import typer

from memcommit.atomize import (
    AtomizeAnalysisSession,
    AtomizeImpactReport,
    AtomizeItem,
)
from memcommit.interfaces.console.text import (
    safe_terminal_text,
)


_CLASSIFICATION_COLORS = {
    "ATOMIC": typer.colors.GREEN,
    "COMPOSITE": typer.colors.YELLOW,
    "UNCERTAIN": typer.colors.RED,
    "NON_PROPOSITIONAL": typer.colors.CYAN,
}

_APPLY_RESULT_SAMPLE_LIMIT = 3


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return singular if count == 1 else (plural or f"{singular}s")


def _render_apply_content(prefix: str, content: str) -> None:
    """Render one selected full Memory without allowing terminal injection."""

    lines = safe_terminal_text(content).splitlines() or [""]
    typer.echo(prefix + lines[0])
    continuation = " " * len(prefix)
    for line in lines[1:]:
        typer.echo(continuation + line)


def render_atomize_apply_result(
    *,
    session: AtomizeAnalysisSession,
    context_name: str,
    result,
    checkpoint_uid: str,
    created: bool,
    unresolved_at_apply_count: int,
    recovered_application: bool = False,
) -> None:
    """Render one typed application result without owning its execution."""

    typer.secho(
        f"ATOMIZE APPLIED · {context_name}",
        fg=typer.colors.GREEN,
        bold=True,
    )
    typer.echo(
        f"EFFECTS · SPLIT {result.split_count} · "
        f"CHILDREN {result.child_count} · KEEP {result.preserved_count}"
    )
    if unresolved_at_apply_count:
        typer.secho(
            f"JUDGMENTS · {unresolved_at_apply_count} unresolved "
            f"{'finding' if unresolved_at_apply_count == 1 else 'findings'} "
            "recorded as applied-as-is",
            fg=typer.colors.YELLOW,
        )
    typer.echo(f"RECEIPT · {session.uid}")
    typer.echo(f"CHECKPOINT · {checkpoint_uid}")
    typer.echo(f"REVIEW · mem review atomize --context {context_name}")
    typer.echo("RECOVERY · mem undo")
    if recovered_application:
        typer.secho(
            "RECOVERY STATUS · prior checkpoint recovered; no duplicate write",
            fg=typer.colors.YELLOW,
        )
    if created:
        typer.echo(f"CONTEXT · CREATED AND CURRENT · {context_name}")


def _render_source(item: AtomizeItem) -> None:
    for line in safe_terminal_text(item.memory.content).splitlines() or [""]:
        if item.classification == "COMPOSITE":
            typer.secho(f"       - {line}", fg=typer.colors.RED)
        else:
            typer.echo(f"         {line}")


def _render_children(item: AtomizeItem) -> None:
    for index, child in enumerate(item.children, start=1):
        lines = safe_terminal_text(child.content).splitlines() or [""]
        typer.secho(
            f"       + {index}. {lines[0]}",
            fg=typer.colors.GREEN,
        )
        for line in lines[1:]:
            typer.secho(f"            {line}", fg=typer.colors.GREEN)
        typer.secho(
            "         Cited source spans: "
            + " | ".join(safe_terminal_text(span) for span in child.source_spans),
            dim=True,
        )
        if child.frame_spans:
            typer.secho(
                "         Cited declared-frame spans: "
                + " | ".join(safe_terminal_text(span) for span in child.frame_spans),
                dim=True,
            )


def _render_item(item: AtomizeItem) -> None:
    color = _CLASSIFICATION_COLORS[item.classification]
    typer.echo()
    typer.secho(
        f"  {item.action:<15} {item.classification:<18} [{item.memory.uid[:8]}]",
        fg=color,
        bold=True,
    )
    _render_source(item)
    if item.children:
        _render_children(item)
        typer.secho(
            "         Status: SAVED PREVIEW — explicit --save/--save-as "
            "applies this locally validated proposal; no second semantic "
            "judge runs in this prototype.",
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
    typer.secho(
        f"         Reason: {safe_terminal_text(item.reason)}",
        dim=True,
    )


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
        f"Atomize impact: {safe_terminal_text(report.context_name)}",
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
        item for item in report.items if show_all or item.classification != "ATOMIC"
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

    if counts["UNCERTAIN"]:
        typer.echo()
        typer.secho(
            "  Review uncertain items with: mem review atomize",
            fg=typer.colors.CYAN,
        )

    typer.echo()
    typer.echo("This inspection applied no changes and created no checkpoint.")
