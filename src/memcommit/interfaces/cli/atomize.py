"""Trusted terminal rendering for provisional atomize impact reports."""

from __future__ import annotations

import typer

from memcommit.application.operations.atomize.domain import (
    AtomizeAnalysisSession,
    AtomizeImpactReport,
    AtomizeItem,
)
from memcommit.interfaces.console.text import (
    safe_terminal_text,
)
from memcommit.interfaces.console.theme import (
    SemanticColorRole,
    memory_object_color_rgb,
    semantic_color_rgb,
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


def _render_apply_memory(
    action: str,
    uid: str,
    content: str,
    *,
    role: SemanticColorRole,
) -> None:
    """Render one exact applied Memory with independently styled semantics."""

    lines = safe_terminal_text(content).splitlines() or [""]
    plain_prefix = f"  {action:<6} · [{uid[:8]}] "
    styled_action = typer.style(
        f"{action:<6}",
        fg=semantic_color_rgb(role),
        bold=True,
    )
    styled_prefix = f"  {styled_action} · [{uid[:8]}] "
    typer.echo(
        styled_prefix
        + typer.style(lines[0], fg=memory_object_color_rgb())
    )
    # ANSI bytes in the styled prefix are not terminal columns, so continuation
    # indentation must be based on the equivalent plain prefix.
    continuation = " " * len(plain_prefix)
    for line in lines[1:]:
        typer.echo(
            continuation
            + typer.style(line, fg=memory_object_color_rgb())
        )


def _render_applied_splits(*, session: AtomizeAnalysisSession, result) -> None:
    """Show a bounded proof of the exact source-to-child effects."""

    sources = {item.memory_uid: item for item in session.items}
    splits = tuple(
        item for item in result.items if item.classification == "COMPOSITE"
    )
    if len(splits) != result.split_count:
        raise ValueError("Atomize split count does not match its applied items.")

    for index, item in enumerate(splits[:_APPLY_RESULT_SAMPLE_LIMIT], start=1):
        source = sources.get(item.source_uid)
        if source is None:
            raise ValueError("Atomize applied source is missing from its analysis.")
        if len(item.result_uids) != len(item.result_contents):
            raise ValueError("Atomize child identities and contents must align.")
        typer.echo("")
        typer.echo(f"SPLIT {index}")
        _render_apply_memory(
            "REMOVE",
            item.source_uid,
            source.content,
            role=SemanticColorRole.REMOVE,
        )
        for uid, content in zip(
            item.result_uids,
            item.result_contents,
            strict=True,
        ):
            _render_apply_memory(
                "ADD",
                uid,
                content,
                role=SemanticColorRole.ADD,
            )

    remaining = len(splits) - min(len(splits), _APPLY_RESULT_SAMPLE_LIMIT)
    if remaining:
        typer.echo("")
        typer.echo(
            f"… {remaining} MORE {_plural(remaining, 'SPLIT').upper()} · see REVIEW"
        )


def render_atomize_apply_result(
    *,
    session: AtomizeAnalysisSession,
    context_name: str,
    result,
    checkpoint_uid: str,
    created: bool,
    unresolved_at_apply_count: int,
    recovered_application: bool = False,
    exact_prewarm: bool = False,
) -> None:
    """Render one typed application result without owning its execution."""

    typer.secho(
        f"ATOMIZE APPLIED · {context_name}",
        bold=True,
    )
    normal_form = getattr(result, "normal_form", None)
    effects = (
        f"EFFECTS · SPLIT {result.split_count} · "
        f"CHILDREN {result.child_count} · KEEP {result.preserved_count}"
    )
    if normal_form is not None:
        effects += (
            f" · DEDUN GROUPS {normal_form.dedun_group_count}"
            f" · ABSORBED {normal_form.absorbed_count}"
        )
    typer.echo(effects)
    if normal_form is not None:
        typer.echo("NORMAL FORM · SEMANTIC CHUNK + DEDUN · VERIFIED")
    if exact_prewarm:
        typer.echo("ANALYSIS · EXACT PREWARM · INITIAL ANALYSIS REUSED")
    if unresolved_at_apply_count:
        typer.secho(
            f"JUDGMENTS · {unresolved_at_apply_count} unresolved "
            f"{'finding' if unresolved_at_apply_count == 1 else 'findings'} "
            "recorded as applied-as-is",
            fg=typer.colors.YELLOW,
        )
    _render_applied_splits(session=session, result=result)
    if result.split_count:
        typer.echo("")
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
            "projects this split, applies typed Dedun policy, and verifies "
            "the affected semantic normal form before one publication.",
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
