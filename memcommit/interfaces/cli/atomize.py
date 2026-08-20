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
    created: bool,
    unresolved_at_apply_count: int,
    recovered_application: bool = False,
) -> None:
    """Render one typed application result without owning its execution."""

    action = "Created and atomized" if created else "Applied atomize analysis to"
    typer.secho(
        f"{action} '{context_name}' from analysis [{session.uid[:8]}].",
        fg=typer.colors.GREEN,
        bold=True,
    )
    typer.echo(
        f"  {result.split_count} "
        f"{'split' if result.split_count == 1 else 'splits'} "
        f"-> {result.child_count} children"
    )
    typer.echo(f"  {result.preserved_count} Memories preserved in place")
    if unresolved_at_apply_count:
        typer.secho(
            f"  Applied as is with {unresolved_at_apply_count} unresolved "
            f"{'finding' if unresolved_at_apply_count == 1 else 'findings'} "
            "recorded",
            fg=typer.colors.YELLOW,
        )
    split_items = [item for item in result.items if item.classification == "COMPOSITE"]
    for item in split_items[:_APPLY_RESULT_SAMPLE_LIMIT]:
        source = session.item_for(item.source_uid)
        if source is None:
            continue
        _render_apply_content(f"  [{item.source_uid[:8]}] ", source.content)
        for uid, content in zip(
            item.result_uids,
            item.result_contents,
            strict=True,
        ):
            _render_apply_content(f"    -> [{uid[:8]}] ", content)
    hidden_split_count = max(0, len(split_items) - _APPLY_RESULT_SAMPLE_LIMIT)
    if hidden_split_count:
        typer.secho(
            f"  … {hidden_split_count} more "
            f"{_plural(hidden_split_count, 'split')} in mem review atomize",
            dim=True,
        )

    ambiguity_count = sum(issue.kind == "AMBIGUITY" for issue in session.quality_issues)
    conflict_count = sum(issue.kind == "CONFLICT" for issue in session.quality_issues)
    uncertainty_count = sum(
        item.classification == "UNCERTAIN" for item in session.items
    )
    typer.echo(
        "  Review · "
        f"{ambiguity_count} {_plural(ambiguity_count, 'ambiguity', 'ambiguities')}"
        f" · {conflict_count} {_plural(conflict_count, 'conflict')}"
        f" · {uncertainty_count} atomize "
        f"{_plural(uncertainty_count, 'uncertainty', 'uncertainties')}"
    )
    typer.echo("  Full analysis · mem review atomize")
    typer.echo("  Recovery · mem undo")
    if recovered_application:
        typer.secho(
            "  Recovered the exact prior checkpoint; no duplicate was created",
            fg=typer.colors.YELLOW,
        )
    if created:
        typer.echo(
            "One Atomize checkpoint created; no intermediate Context was published."
        )
        typer.echo(f"Switched to '{context_name}'.")
    else:
        typer.echo(
            "One Context checkpoint created. The saved analysis remains linked "
            "for Review."
        )


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
