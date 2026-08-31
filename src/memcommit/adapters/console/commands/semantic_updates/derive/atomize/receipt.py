"""Trusted receipt rendering for one completed Atomize application."""

from __future__ import annotations

import typer

from memcommit.adapters.console.terminal.components.findings import (
    echo_issue_one_line,
)
from memcommit.adapters.console.terminal.core.identity import (
    collision_safe_uid_prefixes,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.terminal.core.theme import (
    SemanticColorRole,
    memory_object_color_rgb,
    semantic_color_rgb,
)
from memcommit.application.capabilities.memory_issue_analysis.report import (
    QualityFindingReportItem,
    QualityFindingSource,
)
from memcommit.application.operations.semantic_updates.derive.atomize.application import (
    AtomizeApplicationAudit,
)
from memcommit.application.operations.semantic_updates.derive.atomize.domain import AtomizeAnalysisSession


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
    typer.echo(styled_prefix + typer.style(lines[0], fg=memory_object_color_rgb()))
    # ANSI bytes in the styled prefix are not terminal columns, so continuation
    # indentation must be based on the equivalent plain prefix.
    continuation = " " * len(plain_prefix)
    for line in lines[1:]:
        typer.echo(continuation + typer.style(line, fg=memory_object_color_rgb()))


def _render_applied_splits(*, session: AtomizeAnalysisSession, result) -> None:
    """Show a bounded proof of the exact source-to-child effects."""

    sources = {item.memory_uid: item for item in session.items}
    splits = tuple(item for item in result.items if item.classification == "COMPOSITE")
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
        for uid, content in zip(item.result_uids, item.result_contents, strict=True):
            _render_apply_memory("ADD", uid, content, role=SemanticColorRole.ADD)

    remaining = len(splits) - min(len(splits), _APPLY_RESULT_SAMPLE_LIMIT)
    if remaining:
        typer.echo("")
        typer.echo(
            f"… {remaining} MORE {_plural(remaining, 'SPLIT').upper()} · see REVIEW"
        )


def _unresolved_issue_items(
    session: AtomizeAnalysisSession,
    audit: AtomizeApplicationAudit,
) -> tuple[QualityFindingReportItem, ...]:
    """Project the frozen Apply audit without inventing resolution semantics."""

    source_by_uid = {item.memory_uid: item for item in session.items}
    ordinal_by_uid = {
        item.memory_uid: getattr(item, "position", index) + 1
        for index, item in enumerate(session.items)
    }
    projected: list[QualityFindingReportItem] = []
    for entry in audit.unresolved_at_apply:
        issue_uid = entry.get("issue_uid")
        kind = entry.get("kind")
        source_uids = entry.get("source_uids")
        classification = entry.get("classification")
        reason = entry.get("reason")
        if (
            not isinstance(issue_uid, str)
            or not issue_uid
            or not isinstance(kind, str)
            or not kind
            or not isinstance(source_uids, list)
            or not source_uids
            or any(not isinstance(uid, str) or not uid for uid in source_uids)
            or not isinstance(classification, str)
            or not classification
            or not isinstance(reason, str)
            or not reason
        ):
            raise ValueError(
                "Atomize Apply audit contains an invalid unresolved issue."
            )
        missing = [uid for uid in source_uids if uid not in source_by_uid]
        if missing:
            raise ValueError(
                "Atomize Apply audit references an unavailable Source Memory."
            )
        category = "conflicts" if kind == "CONFLICT" else "ambiguities"
        projected.append(
            QualityFindingReportItem(
                uid=issue_uid,
                category=category,
                kind=kind,
                classification=classification,
                title=kind.replace("_", " "),
                reason_heading="WHY",
                reason=reason,
                sources=tuple(
                    QualityFindingSource(
                        label=f"SOURCE {index}",
                        context_name=session.context_name,
                        memory_uid=source_uid,
                        content=source_by_uid[source_uid].content,
                        ordinal=ordinal_by_uid[source_uid],
                    )
                    for index, source_uid in enumerate(source_uids, start=1)
                ),
            )
        )
    return tuple(projected)


def _render_unresolved_issues(
    session: AtomizeAnalysisSession,
    audit: AtomizeApplicationAudit,
) -> None:
    items = _unresolved_issue_items(session, audit)
    if not items:
        return
    typer.secho(
        f"UNRESOLVED ISSUES · {len(items)} · APPLIED AS-IS",
        fg=typer.colors.YELLOW,
        bold=True,
    )
    uid_prefixes = collision_safe_uid_prefixes(
        source.memory_uid for item in items for source in item.sources
    )
    for item in items:
        echo_issue_one_line(
            item,
            prefix="  ",
            show_context=False,
            uid_prefixes=uid_prefixes,
        )


def render_atomize_apply_result(
    *,
    session: AtomizeAnalysisSession,
    context_name: str,
    result,
    checkpoint_uid: str,
    created: bool,
    audit: AtomizeApplicationAudit,
    recovered_application: bool = False,
    exact_prewarm: bool = False,
) -> None:
    """Render one typed application receipt without owning its execution."""

    if not isinstance(audit, AtomizeApplicationAudit):
        raise TypeError("Atomize receipt requires a typed application audit.")
    typer.secho(f"ATOMIZE APPLIED · {context_name}", bold=True)
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
    _render_unresolved_issues(session, audit)
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


__all__ = ["render_atomize_apply_result"]
