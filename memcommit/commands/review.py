"""Create or resume the shared terminal shell for semantic review."""
from __future__ import annotations

from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.review_shell import (
    ReviewCancelled,
    render_review_snapshot,
    run_review_shell,
)
from memcommit.findings import FindingsError
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.review import (
    ReviewError,
    create_ambiguity_review,
    review_matches_context,
)
from memcommit.store import MemoryStore


def _load_direct_context(
    store: MemoryStore,
    context_name: str | None,
):
    return (
        store.load_current_direct()
        if context_name is None
        else store.load_direct(context_name)
    )


def cmd(
    kind: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Start a new review adapter (currently: ambiguities); "
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
) -> None:
    """Stage review annotations without editing or checkpointing Memories."""
    store = MemoryStore()
    try:
        if kind is None:
            if replace_review:
                raise ReviewError(
                    "--replace-review is valid only when starting an adapter."
                )
            session = store.load_review_session()
            if session is None:
                raise ReviewError(
                    "No saved review exists. Start one with "
                    "'mem review ambiguities'."
                )
            if (
                context_name is not None
                and context_name != session.context_name
            ):
                raise ReviewError(
                    "The saved review belongs to a different Context."
                )
            ctx = store.load_direct(session.context_name)
        else:
            normalized_kind = kind.casefold()
            if normalized_kind not in {"ambiguity", "ambiguities"}:
                raise ReviewError(
                    "Unsupported review adapter. "
                    "The implemented adapter is 'ambiguities'."
                )
            # Explicit replacement is also the recovery path for a malformed
            # prior artifact, so do not require that artifact to parse first.
            existing = (
                None
                if replace_review
                else store.load_review_session()
            )
            if existing is not None and not replace_review:
                raise ReviewError(
                    "A saved review already exists. Resume it with "
                    "'mem review', or explicitly replace it with "
                    "'mem review ambiguities --replace-review'."
                )
            ctx = _load_direct_context(store, context_name)
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
        RuntimeError,
        ValueError,
        FindingsError,
        QueryProviderError,
        ReviewError,
    ) as error:
        typer.secho(
            f"Review error: {error}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if not review_matches_context(session, ctx):
        typer.secho(
            "Review error: the saved review is stale because its Context "
            "identity, direct Memory contents, or canonical order changed. "
            "Start a new review with 'mem review ambiguities'.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

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
        f"Review saved: {session.answered_count}/{len(session.items)} "
        "items answered.",
        fg=typer.colors.GREEN,
        bold=True,
    )
    typer.echo("No Memory changes applied. No checkpoint created.")
