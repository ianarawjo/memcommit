"""Render the active staged or locally applied update without a model."""
from __future__ import annotations

import difflib
import json
from typing import Annotated

import typer

from memcommit.interfaces.console.identity import collision_safe_uid_prefixes
from memcommit.interfaces.console.theme import (
    SemanticColorRole,
    semantic_color_rgb,
)
from memcommit.store import MemoryStore
from memcommit.operations.update.granted_application import inspect_granted_update
from memcommit.reviewing.memory_diff import (
    MemoryChange,
    memory_diff_lines,
    update_operation_change,
)
from memcommit.commands.checkpoint_diff import render_checkpoint_revision_cli
from memcommit.commands.history_present import checkpoint_picker_entries
from memcommit.commands.update_render import render_plan
from memcommit.context_locator import resolve_context_locator
from memcommit.context_targeting.checkpoint import (
    resolve_local_checkpoint_target,
    resolve_local_context_checkpoint_target,
)
from memcommit.context_targeting.model import CheckpointTarget
from memcommit.context_targeting.uid_locator import resolve_exact_or_unique_uid
from memcommit.operations.update.model import (
    AddOperation,
    EditOperation,
    RemoveOperation,
    UpdateSession,
    applied_session_matches,
    count_operations,
    session_matches,
)


def _short_uid_map(session: UpdateSession) -> dict[str, str]:
    """Return collision-safe UID prefixes, using at least eight characters."""
    uids = {
        operation.memory_uid
        for operation in session.operations
    }
    uids.update(
        source.memory_uid
        for operation in session.operations
        for source in operation.source_refs
    )
    return collision_safe_uid_prefixes(uids)


def _shown_uid(
    uid: str,
    prefixes: dict[str, str],
    *,
    verbose: bool,
) -> str:
    return uid if verbose else prefixes.get(uid, uid[:8])


def _summary(session: UpdateSession) -> str:
    edits, additions, removals = count_operations(session)
    total = edits + additions + removals
    return (
        f"{total} change{'s' if total != 1 else ''} · "
        f"{edits} edited · {additions} added · {removals} removed"
    )


def _render_header(session: UpdateSession, *, verbose: bool) -> None:
    heading = (
        (
            "Applied granted update"
            if (
                session.granted_source is not None
                or session.granted_target is not None
            )
            else "Applied local update"
        )
        if session.status == "applied"
        else "Undone update"
        if session.status == "undone"
        else "Update preview"
    )
    typer.secho(heading, fg=typer.colors.CYAN, bold=True)
    typer.secho(
        f"{session.source_name} → {session.target_name}",
        bold=True,
    )
    typer.echo(_summary(session))
    if verbose:
        typer.secho(f"Update  {session.uid}", dim=True)
        typer.secho(
            f"Source  {session.source_uid}  {session.source_digest}",
            dim=True,
        )
        typer.secho(
            f"Base    {session.target_uid}  {session.target_digest}",
            dim=True,
        )
        if session.application is not None:
            typer.secho(
                f"Result  {session.target_uid}  "
                f"{session.application.target_digest}",
                dim=True,
            )
            for checkpoint in session.application.checkpoints:
                typer.secho(
                    f"Checkpoint  {checkpoint.context_name}  "
                    f"{checkpoint.checkpoint_uid}",
                    dim=True,
                )
        if session.granted_source is not None:
            typer.secho(
                "Source Grant   "
                f"{session.granted_source.grant_uid}  "
                f"authority {session.granted_source.authority_profile_uid}",
                dim=True,
            )
        if session.granted_target is not None:
            typer.secho(
                "Target Grant   "
                f"{session.granted_target.grant_uid}  "
                f"authority {session.granted_target.authority_profile_uid}",
                dim=True,
            )


def _render_semantic_change(change: MemoryChange) -> None:
    """Render shared mechanical hunks with CLI-specific ANSI emphasis."""

    for line in memory_diff_lines(change):
        color = (
            typer.colors.RED
            if line.marker == "-"
            else typer.colors.GREEN
            if line.marker == "+"
            else None
        )
        prefix = "    " if line.marker == " " else f"  {line.marker} "
        parts = [typer.style(prefix, fg=color, dim=line.marker in {" ", "="})]
        parts.extend(
            typer.style(
                span.text,
                fg=color,
                bold=span.changed and line.marker in {"-", "+"},
                dim=line.marker in {" ", "="},
            )
            for span in line.spans
        )
        typer.echo("".join(parts))

    if change.before is None or change.after is None:
        return
    old_terminal_newline = change.before.endswith(("\n", "\r"))
    new_terminal_newline = change.after.endswith(("\n", "\r"))
    if old_terminal_newline != new_terminal_newline:
        change = "added" if new_terminal_newline else "removed"
        typer.secho(f"    terminal newline {change}", dim=True)


def _render_metadata(
    operation: EditOperation | AddOperation | RemoveOperation,
    prefixes: dict[str, str],
    *,
    verbose: bool,
) -> None:
    sources = ", ".join(
        f"{source.context_name} "
        f"[{_shown_uid(source.memory_uid, prefixes, verbose=verbose)}]"
        for source in operation.source_refs
    )
    typer.secho(f"  Source  {sources}", fg=typer.colors.CYAN)
    typer.secho(f"  Reason  {operation.reason}", dim=True)


def _render_semantic_operation(
    operation: EditOperation | AddOperation | RemoveOperation,
    prefixes: dict[str, str],
    *,
    verbose: bool,
) -> None:
    change = update_operation_change(operation)
    shown_uid = _shown_uid(
        change.memory_uid,
        prefixes,
        verbose=verbose,
    )
    if isinstance(operation, EditOperation):
        typer.secho(
            f"EDIT  {change.location}  [{shown_uid}]",
            fg=semantic_color_rgb(SemanticColorRole.EDIT),
            bold=True,
        )
        _render_semantic_change(change)
    elif isinstance(operation, AddOperation):
        typer.secho(
            f"ADD   {change.location}  [new:{shown_uid}]",
            fg=semantic_color_rgb(SemanticColorRole.ADD),
            bold=True,
        )
        _render_semantic_change(change)
    else:
        typer.secho(
            f"REMOVE {change.location}  [{shown_uid}]",
            fg=semantic_color_rgb(SemanticColorRole.REMOVE),
            bold=True,
        )
        _render_semantic_change(change)
    typer.echo()
    _render_metadata(operation, prefixes, verbose=verbose)


def _memory_label(context_name: str, memory_uid: str) -> str:
    return f"{context_name}#{memory_uid}"


def _encoded_lines(content: str) -> list[str]:
    """Encode line text and its terminator so raw diff preserves newlines."""
    encoded: list[str] = []
    for line in content.splitlines(keepends=True):
        if line.endswith("\r\n"):
            text = line[:-2]
            has_newline = True
        elif line.endswith("\n") or line.endswith("\r"):
            text = line[:-1]
            has_newline = True
        else:
            text = line
            has_newline = False
        encoded.append(
            json.dumps(
                [text, has_newline],
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    return encoded


def _unified_lines(
    operation: EditOperation | AddOperation | RemoveOperation,
) -> list[str]:
    label = _memory_label(
        operation.owner_context_name,
        operation.memory_uid,
    )
    if isinstance(operation, EditOperation):
        old_lines = _encoded_lines(operation.old_content)
        new_lines = _encoded_lines(operation.new_content)
        from_file = f"a/{label}"
        to_file = f"b/{label}"
    elif isinstance(operation, AddOperation):
        old_lines = []
        new_lines = _encoded_lines(operation.new_content)
        from_file = "/dev/null"
        to_file = f"b/{label}"
    else:
        old_lines = _encoded_lines(operation.old_content)
        new_lines = []
        from_file = f"a/{label}"
        to_file = "/dev/null"
    return list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=from_file,
            tofile=to_file,
            lineterm="",
        )
    )


def _render_raw_line(line: str) -> None:
    if line.startswith("--- ") or line.startswith("+++ "):
        typer.secho(line, bold=True)
    elif line.startswith("@@"):
        typer.secho(line, fg=typer.colors.CYAN)
    elif line.startswith("+"):
        typer.secho(line, fg=typer.colors.GREEN)
    elif line.startswith("-"):
        typer.secho(line, fg=typer.colors.RED)
    else:
        typer.echo(line)


def _render_encoded_raw_line(line: str) -> None:
    if not line or line[0] not in {" ", "+", "-"}:
        _render_raw_line(line)
        return
    try:
        value = json.loads(line[1:])
    except json.JSONDecodeError:
        _render_raw_line(line)
        return
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not isinstance(value[0], str)
        or not isinstance(value[1], bool)
    ):
        _render_raw_line(line)
        return
    rendered = f"{line[0]}{value[0]}"
    if line[0] == "+":
        typer.secho(rendered, fg=typer.colors.GREEN)
    elif line[0] == "-":
        typer.secho(rendered, fg=typer.colors.RED)
    else:
        typer.echo(rendered)
    if not value[1]:
        typer.echo("\\ No newline at end of file")


def _render_raw_operation(
    operation: EditOperation | AddOperation | RemoveOperation,
) -> None:
    label = _memory_label(
        operation.owner_context_name,
        operation.memory_uid,
    )
    typer.secho(f"diff --mem {label}", bold=True)
    if isinstance(operation, AddOperation):
        typer.secho("new memory", dim=True)
    elif isinstance(operation, RemoveOperation):
        typer.secho("removed memory", dim=True)
    for line in _unified_lines(operation):
        if (
            line.startswith("--- ")
            or line.startswith("+++ ")
            or line.startswith("@@")
        ):
            _render_raw_line(line)
        else:
            _render_encoded_raw_line(line)
    sources = ", ".join(
        f"{source.context_name}#{source.memory_uid}"
        for source in operation.source_refs
    )
    typer.secho(f"Sources: {sources}", dim=True)
    typer.secho(f"Reason: {operation.reason}", dim=True)


def render_diff(
    session: UpdateSession,
    *,
    raw: bool = False,
    stat: bool = False,
    verbose: bool = False,
) -> None:
    """Render one validated staged or locally applied session."""
    if not raw and not stat and not verbose:
        render_plan(
            session,
            staged=session.status == "staged",
            applied=session.status == "applied",
            undone=session.status == "undone",
        )
        return
    _render_header(session, verbose=verbose)
    if stat:
        return
    if not session.operations:
        message = (
            "No local changes were needed."
            if session.status == "applied"
            else "No staged changes."
        )
        typer.echo(f"\n{message}")
        return

    prefixes = _short_uid_map(session)
    for index, operation in enumerate(session.operations):
        typer.echo()
        if raw:
            _render_raw_operation(operation)
        else:
            _render_semantic_operation(
                operation,
                prefixes,
                verbose=verbose,
            )
        if index != len(session.operations) - 1:
            typer.echo()
            typer.secho("─" * 64, dim=True)


def cmd(
    target: Annotated[
        str | None,
        typer.Argument(
            help=(
                "Existing Context, or CHECKPOINT when --context is supplied"
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
            help="Show full UIDs and source/target fingerprints",
        ),
    ] = False,
) -> None:
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
        # active Update or current Context exists yet.
        current_context = None
    checkpoint_selector = checkpoint_uid
    context_locator = context_name
    if context_name is not None and target is not None:
        checkpoint_selector = target
    elif context_name is None and checkpoint_uid is not None and target is not None:
        context_locator = target
    elif context_name is None and checkpoint_uid is None and target is not None:
        try:
            resolved_target = resolve_local_context_checkpoint_target(
                store,
                target,
                current=current_context,
            )
        except ValueError as error:
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
        except ValueError as error:
            typer.secho(f"Diff error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        context_locator = inferred_checkpoint.context_name
        checkpoint_selector = inferred_checkpoint.checkpoint_uid

    history_requested = context_locator is not None or checkpoint_selector is not None
    if context_locator is not None:
        try:
            context_locator = resolve_context_locator(
                context_locator,
                current=current_context,
            )
        except ValueError as error:
            typer.secho(f"Diff error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)

    if history_requested:
        try:
            canonical_context = resolve_context_locator(
                context_locator,
                current=current_context,
            )
            checkpoints = store.list_checkpoints(canonical_context)
            entries = checkpoint_picker_entries(checkpoints)
            if not entries:
                raise ValueError(
                    f"Context '{canonical_context}' has no checkpoints."
                )
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
            typer.echo(
                render_checkpoint_revision_cli(
                    checkpoints,
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
        return

    try:
        session = store.load_staged_update()
    except (OSError, ValueError) as error:
        typer.secho(f"Diff error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    if session is None:
        typer.secho(
            "Diff error: no local update. Run 'mem update --to <context>' "
            "first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if session.status not in {"staged", "applied", "undone"}:
        typer.secho(
            "Diff error: the saved record is not an update result.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    inspection_status = "current"
    if session.granted_source is not None or session.granted_target is not None:
        inspection_status = inspect_granted_update(store, session).status
        fresh = inspection_status == "current"
    else:
        fresh = False
        try:
            source = store.load(session.source_name)
            target = store.load(session.target_name)
            if session.status == "applied":
                fresh = applied_session_matches(session, source, target)
            else:
                fresh = session_matches(session, source, target)
        except (OSError, ValueError):
            fresh = False

    if not fresh:
        timing = (
            "after this update was applied"
            if session.status == "applied"
            else "after this update was undone"
            if session.status == "undone"
            else "after this update was staged"
        )
        status_label = (
            "REVOKED — saved grant is no longer available"
            if inspection_status == "revoked"
            else f"STALE — source or target changed {timing}"
        )
        typer.secho(
            status_label,
            fg=typer.colors.YELLOW,
            bold=True,
            err=True,
        )
    render_diff(
        session,
        raw=raw,
        stat=stat,
        verbose=verbose,
    )
    if not fresh:
        guidance = (
            "The recorded diff remains inspectable, but it cannot be treated "
            "as a current applied result. Re-run impact/update only after "
            "access and endpoints are current."
            if (
                session.granted_source is not None
                or session.granted_target is not None
            )
            else (
                "Review the local fork and re-run impact/update before "
                "contributing."
            )
        )
        typer.secho(
            guidance,
            fg=typer.colors.YELLOW,
            err=True,
        )
        raise typer.Exit(1)
