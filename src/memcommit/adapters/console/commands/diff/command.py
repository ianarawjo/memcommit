"""Inspect one exact Context checkpoint revision without a model."""

from __future__ import annotations

from typing import Annotated

import typer

from memcommit.adapters.console.terminal.components.history.checkpoint_diff import (
    open_checkpoint_revision_viewer,
    render_checkpoint_revision_cli,
)
from memcommit.adapters.console.terminal.components.history.presentation import (
    checkpoint_picker_entries,
)
from memcommit.adapters.console.terminal.components.read_only_viewer import (
    interactive_report_terminal,
)
from memcommit.application.authorization.checkpoint_read import (
    authorize_checkpoint_read,
)
from memcommit.application.authorization.checkpoint_read_model import CheckpointRead
from memcommit.application.capabilities.history.query.checkpoint_history_slicing import (
    build_checkpoint_history_slice,
)
from memcommit.application.context_access.operand_resolution import (
    freeze_profile_context_access_candidates,
    resolve_existing_context_access,
)
from memcommit.application.operations.diff.context_checkpoint_lookup import (
    resolve_local_checkpoint_target,
    resolve_local_context_checkpoint_target,
)
from memcommit.core.context_targeting.model import CheckpointTarget
from memcommit.core.context_targeting.uid_locator import resolve_exact_or_unique_uid
from memcommit.persistence.store import MemoryStore


def cmd(
    target: Annotated[
        str | None,
        typer.Argument(
            help=(
                "Existing Context name/UID or checkpoint UID; defaults to the "
                "current Context"
            )
        ),
    ] = None,
    context_name: Annotated[
        str | None,
        typer.Option(
            "--context",
            "-c",
            help="Existing Context that owns an explicit checkpoint",
        ),
    ] = None,
    checkpoint_uid: Annotated[
        str | None,
        typer.Option(
            "--checkpoint",
            help="Exact checkpoint UID or unambiguous prefix",
        ),
    ] = None,
    raw: Annotated[
        bool,
        typer.Option(
            "--raw",
            help="Show the exact Git-style unified diff",
        ),
    ] = False,
    stat: Annotated[
        bool,
        typer.Option(
            "--stat",
            help="Show only the change summary",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Include unchanged Memories and complete UIDs",
        ),
    ] = False,
) -> None:
    """Show one checkpoint's pre-image-to-result revision."""

    if raw and stat:
        typer.secho(
            "Diff error: '--raw' and '--stat' cannot be used together.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if target is not None and context_name is not None and checkpoint_uid is not None:
        typer.secho(
            "Diff error: pass the checkpoint either as the operand or with "
            "--checkpoint, not both.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)

    store = MemoryStore(create=False)
    try:
        current_context = store.current_context_name()
    except FileNotFoundError:
        # Read-only Diff must not create a Profile merely to discover that no
        # current Context exists.
        current_context = None

    checkpoint_selector = checkpoint_uid
    context_locator = context_name
    if context_name is not None and target is not None:
        checkpoint_selector = target
    elif context_name is None and checkpoint_uid is not None and target is not None:
        context_locator = target
    elif context_name is None and checkpoint_uid is None and target is not None:
        try:
            context_candidates = freeze_profile_context_access_candidates(
                store,
                current_name=current_context,
            )
            resolved_target = resolve_local_context_checkpoint_target(
                store,
                target,
                current=current_context,
                context_candidates=context_candidates,
            )
        except (FileNotFoundError, ValueError) as error:
            typer.secho(f"Diff error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        if isinstance(resolved_target, CheckpointTarget):
            context_locator = resolved_target.context_name
            checkpoint_selector = resolved_target.checkpoint_uid
        else:
            context_locator = resolved_target.context_name
    elif checkpoint_uid is not None and context_name is None:
        try:
            inferred_checkpoint = resolve_local_checkpoint_target(
                store,
                checkpoint_uid,
            )
        except (FileNotFoundError, ValueError) as error:
            typer.secho(f"Diff error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        context_locator = inferred_checkpoint.context_name
        checkpoint_selector = inferred_checkpoint.checkpoint_uid
    elif context_locator is None:
        context_locator = current_context

    if context_locator is None:
        typer.secho(
            "Diff error: no current Context. Pass a Context name/UID or "
            "checkpoint UID.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    try:
        resolved_context = resolve_existing_context_access(
            store,
            context_locator,
            current_name=current_context,
            required_permission="READ",
        )
        canonical_context = resolved_context.name
        access = resolved_context.value
        history = build_checkpoint_history_slice(
            access.store,
            access.context_name,
        )
        entries = checkpoint_picker_entries(history.physical_entries)
        if not entries:
            raise ValueError(f"Context '{canonical_context}' has no checkpoints.")
        entry = (
            entries[0]
            if checkpoint_selector is None
            else resolve_exact_or_unique_uid(
                entries,
                checkpoint_selector,
                uid=lambda candidate: candidate.uid,
                label="Checkpoint",
            )
        )
        authorize_checkpoint_read(
            access,
            CheckpointRead.reference(history.context_uid, (entry.uid,)),
            history,
        )
        if not raw and not stat and interactive_report_terminal():
            open_checkpoint_revision_viewer(
                history,
                entry,
                context_name=canonical_context,
                verbose=verbose,
            )
            return
        typer.echo(
            render_checkpoint_revision_cli(
                history,
                entry,
                context_name=canonical_context,
                stat=stat,
                raw=raw,
                verbose=verbose,
            )
        )
    except (OSError, RuntimeError, ValueError) as error:
        typer.secho(f"Diff error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
