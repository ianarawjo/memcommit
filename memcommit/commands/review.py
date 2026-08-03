"""Create or resume the shared terminal shell for semantic review."""

from __future__ import annotations

import sys
from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.atomize import (
    AtomizeImpactError,
    atomize_analysis_matches_context,
)
from memcommit.atomize_workbench import (
    AtomizeWorkbenchError,
    atomize_workbench_issue_projection,
    create_atomize_workbench,
    project_atomize_workbench_findings,
)
from memcommit.commands.atomize_workbench_shell import (
    render_atomize_workbench_snapshot,
    run_atomize_workbench_shell,
)
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.commands.review_shell import (
    ReviewCancelled,
    render_review_snapshot,
    run_review_shell,
    visible_ordinal_index,
)
from memcommit.commands.tui_primitives import display_escape_text
from memcommit.findings import FindingsError
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.review import (
    ReviewError,
    atomize_review_matches_analysis,
    create_ambiguity_review,
    review_matches_context,
)
from memcommit.store import MemoryStore


def _load_direct_context(
    store: MemoryStore,
    context_name: str | None,
    *,
    current_name: str | None,
):
    selected_name = context_name if context_name is not None else current_name
    if not selected_name:
        raise RuntimeError(
            "No current context. Pass --context or run 'mem init <name>' first."
        )
    return store.load_direct(selected_name)


def _run_atomize_workbench(
    *,
    store: MemoryStore,
    context_name: str | None,
    current_name: str | None,
    snapshot: bool,
    replace: bool,
    respond_to: str | None,
    response: str | None,
) -> None:
    """Resume the Context-bound atomize workbench compatibility adapter."""
    ctx = _load_direct_context(
        store,
        context_name,
        current_name=current_name,
    )
    analysis = store.load_atomize_analysis(ctx.uid)
    if analysis is None:
        raise ReviewError(
            "No saved atomize analysis exists for this Context. Run "
            "'mem impact atomize' or 'mem atomize' first."
        )
    if not atomize_analysis_matches_context(analysis, ctx):
        raise ReviewError(
            "The saved atomize analysis is stale for this Context. Request "
            "an explicit reanalysis before reviewing it."
        )
    workbench = None if replace else store.load_atomize_workbench(analysis)
    if workbench is None:
        workbench = create_atomize_workbench(analysis)
        store.save_atomize_workbench(workbench)
    if not workbench.matches_analysis(
        analysis_uid=analysis.uid,
        context_uid=analysis.context_uid,
        context_name=analysis.context_name,
        context_digest=analysis.context_digest,
        issues=atomize_workbench_issue_projection(analysis),
    ):
        raise ReviewError("The saved atomize workbench does not match its analysis.")
    if (respond_to is None) != (response is None):
        raise ReviewError("--respond-to and --response must be used together.")
    if respond_to is not None:
        selector = respond_to.strip()
        findings = project_atomize_workbench_findings(analysis)
        finding_by_uid = {finding.uid: finding for finding in findings}
        ordered = workbench.ordered_issues()
        selected_index = visible_ordinal_index(selector, len(ordered))
        if selected_index is not None:
            matches = [finding_by_uid[ordered[selected_index].uid]]
        else:
            matches = [
                finding
                for finding in findings
                if finding.uid.startswith(selector)
                or any(
                    source_uid.startswith(selector)
                    for source_uid in finding.source_uids
                )
            ]
        if not selector or len(matches) != 1:
            raise ReviewError(
                "The response target is missing or ambiguous. Use its visible "
                "1-based issue number or a unique issue/source uid prefix."
            )
        workbench.cursor_uid = matches[0].uid
        workbench.response_for(matches[0].uid).text = response or ""
        store.save_atomize_workbench(workbench)
        typer.echo(render_atomize_workbench_snapshot(workbench, analysis))
        return
    if snapshot or not sys.stdin.isatty() or not sys.stdout.isatty():
        typer.echo(render_atomize_workbench_snapshot(workbench, analysis))
        return
    try:
        run_atomize_workbench_shell(
            workbench,
            analysis,
            save=store.save_atomize_workbench,
        )
    except ReviewCancelled:
        typer.echo("Atomize workbench saved. No Memory changes applied.")
        return
    typer.secho(
        f"Atomize workbench saved: {workbench.answered_count}/"
        f"{workbench.issue_count} issues answered.",
        fg=typer.colors.GREEN,
        bold=True,
    )
    typer.echo("No Memory changes applied. No checkpoint created.")


def cmd(
    kind: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Start a review adapter (ambiguities or atomize); "
                "omit to resume the saved review"
            )
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Context to review (defaults to current)",
        ),
    ] = None,
    snapshot: Annotated[
        bool,
        typer.Option(
            "--snapshot",
            help="Print the current review frame without opening the TUI",
        ),
    ] = False,
    replace_review: Annotated[
        bool,
        typer.Option(
            "--replace-review",
            help="Replace an existing saved review when starting a new one",
        ),
    ] = False,
    respond_to: Annotated[
        Optional[str],
        typer.Option(
            "--respond-to",
            help=(
                "Visible issue number or unique issue/source uid prefix to "
                "annotate without opening the TUI"
            ),
        ),
    ] = None,
    response: Annotated[
        Optional[str],
        typer.Option(
            "--response",
            help="Context/comment saved for --respond-to; an empty value clears",
        ),
    ] = None,
) -> None:
    """Stage review annotations without editing or checkpointing Memories."""
    store = MemoryStore()
    try:
        context_snapshot = ContextOperandSnapshot.capture(store)
        canonical_context_name = (
            None if context_name is None else context_snapshot.resolve(context_name)
        )
        normalized_kind = kind.casefold() if kind is not None else None
        if normalized_kind == "atomize":
            _run_atomize_workbench(
                store=store,
                context_name=canonical_context_name,
                current_name=context_snapshot.current_name,
                snapshot=snapshot,
                replace=replace_review,
                respond_to=respond_to,
                response=response,
            )
            return
        if kind is None:
            if replace_review:
                raise ReviewError(
                    "--replace-review is valid only when starting an adapter."
                )
            session = store.load_review_session()
            if session is None:
                _run_atomize_workbench(
                    store=store,
                    context_name=canonical_context_name,
                    current_name=context_snapshot.current_name,
                    snapshot=snapshot,
                    replace=False,
                    respond_to=respond_to,
                    response=response,
                )
                return
            if (
                canonical_context_name is not None
                and canonical_context_name != session.context_name
            ):
                raise ReviewError("The saved review belongs to a different Context.")
            ctx = store.load_direct(session.context_name)
        else:
            if normalized_kind not in {
                "ambiguity",
                "ambiguities",
            }:
                raise ReviewError(
                    "Unsupported review adapter. "
                    "Implemented adapters are 'ambiguities' and 'atomize'."
                )
            # Explicit replacement is also the recovery path for a malformed
            # prior artifact, so do not require that artifact to parse first.
            existing = None if replace_review else store.load_review_session()
            if existing is not None and not replace_review:
                raise ReviewError(
                    "A saved review already exists. Resume it with "
                    "'mem review', or explicitly replace it with "
                    f"'mem review {normalized_kind} --replace-review'."
                )
            ctx = _load_direct_context(
                store,
                canonical_context_name,
                current_name=context_snapshot.current_name,
            )
            report = ops.find_ambiguities(
                ctx,
                connect_codex_chatgpt_provider,
            )
            session = create_ambiguity_review(ctx, report)
            # The semantic report is durable before terminal control begins.
            # A PTY disconnect must not discard the expensive one-shot result.
            store.save_review_session(session)
    except (
        FileNotFoundError,
        OSError,
        RuntimeError,
        ValueError,
        FindingsError,
        AtomizeImpactError,
        AtomizeWorkbenchError,
        QueryProviderError,
        ReviewError,
    ) as error:
        typer.secho(
            f"Review error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    try:
        analysis = (
            store.load_atomize_analysis(ctx.uid) if session.kind == "atomize" else None
        )
    except (OSError, RuntimeError, ValueError) as error:
        typer.secho(
            f"Review error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    matches_source = (
        atomize_review_matches_analysis(session, ctx, analysis)
        if session.kind == "atomize" and analysis is not None
        else (
            review_matches_context(session, ctx)
            if session.kind == "ambiguities"
            else False
        )
    )
    if not matches_source:
        restart = (
            "mem review atomize --replace-review"
            if session.kind == "atomize"
            else "mem review ambiguities --replace-review"
        )
        typer.secho(
            "Review error: the saved review is stale because its Context "
            "or source analysis changed. Start a new review with "
            f"'{restart}'.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if (respond_to is None) != (response is None):
        typer.secho(
            "Review error: --respond-to and --response must be used together.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if respond_to is not None:
        selector = respond_to.strip()
        ordered = session.ordered_items()
        selected_index = visible_ordinal_index(selector, len(ordered))
        if selected_index is not None:
            matches = [ordered[selected_index]]
        else:
            matches = [item for item in session.items if item.uid.startswith(selector)]
        if not selector or len(matches) != 1:
            typer.secho(
                "Review error: the response target is missing or ambiguous. "
                "Use its visible 1-based issue number or a unique uid prefix.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        session.cursor_uid = matches[0].uid
        session.response_for(matches[0].uid).text = response or ""
        try:
            store.save_review_session(session)
        except (OSError, ValueError) as error:
            typer.secho(
                f"Review error: {error}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        typer.echo(render_review_snapshot(session, ctx))
        return

    if snapshot or not session.items:
        typer.echo(render_review_snapshot(session, ctx))
        return

    try:
        run_review_shell(
            session,
            ctx,
            save=store.save_review_session,
        )
    except ReviewCancelled:
        typer.echo("Review saved. No Memory changes applied.")
        return
    except (OSError, ValueError) as error:
        typer.secho(
            f"Review error: {error}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    typer.secho(
        f"Review saved: {session.answered_count}/{len(session.items)} items answered.",
        fg=typer.colors.GREEN,
        bold=True,
    )
    typer.echo("No Memory changes applied. No checkpoint created.")
