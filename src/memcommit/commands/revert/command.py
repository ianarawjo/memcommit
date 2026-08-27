"""Restore one exact checkpoint, optionally selected through history search."""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Mapping
from typing import Annotated, Any, Optional

import typer

from memcommit.commands.shared.checkpoint_diff import (
    checkpoint_revision_detail_renderer,
)
from memcommit.commands.shared.command_progress import CommandProgress
from memcommit.commands.shared.context_operand import ContextOperandSnapshot
from memcommit.commands.shared.diff_browser import browse_checkpoint_locations
from memcommit.commands.shared.history_picker import (
    HistorySelectionReceipt,
    choose_history,
    revert_exact_command_review,
)
from memcommit.commands.shared.history_present import checkpoint_picker_entries
from memcommit.commands.shared.restoration_present import (
    MemoryRefTargetKey,
    memory_ref_target_key,
    render_checkpoint_unit_revert_receipt,
    render_revert_receipt,
)
from memcommit.retained_history.checkpoint_catalog import (
    CheckpointCatalogError,
    CheckpointNotFoundError,
    ResolvedCheckpointUnit,
    freeze_checkpoint_catalog,
)
from memcommit.context import Memory
from memcommit.retained_history.reconstruction import HistoryError, build_history
from memcommit.application.operations.log.search import HistorySearchError, search_history
from memcommit.infrastructure.providers.subscription import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.persistence.store import (
    MemoryStore,
    checkpoint_history_digest,
    context_record_digest,
)


_UID_LIKE = re.compile(r"[0-9a-fA-F-]{8,64}")


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _matching_checkpoint(
    entries: list[dict[str, Any]],
    selector: str,
) -> dict[str, Any] | None:
    matches = [
        entry
        for entry in entries
        if isinstance(entry.get("uid"), str) and entry["uid"].startswith(selector)
    ]
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous prefix '{selector}' matches {len(matches)} checkpoints."
        )
    return matches[0] if matches else None


def _looks_like_missing_uid(selector: str) -> bool:
    return (
        _UID_LIKE.fullmatch(selector) is not None
        and sum(character != "-" for character in selector) >= 8
    )


def _semantic_selection(
    store: MemoryStore,
    name: str,
    entries: list[dict[str, Any]],
    query: str,
    *,
    keep: bool,
) -> HistorySelectionReceipt | None:
    if not _interactive_terminal():
        raise ValueError(
            "Natural-language revert selection requires an interactive "
            "terminal. Inspect candidates with "
            f"'mem log {json.dumps(query, ensure_ascii=False)}', then rerun "
            "'mem revert <checkpoint-uid>'."
        )
    timeline = build_history(store, name)
    with CommandProgress(
        "REVERT",
        "connecting provider",
        total=2,
    ) as progress:
        provider = connect_codex_chatgpt_provider()
        progress.update("searching history", step=2)
        results = search_history(
            timeline,
            query,
            provider,
            result_kinds=("checkpoint",),
            limit=20,
        )
    active_uids = {
        entry["uid"] for entry in entries if isinstance(entry.get("uid"), str)
    }
    selected_uids = [
        result.checkpoint_uid
        for result in results
        if result.selectable and result.checkpoint_uid in active_uids
    ]
    if not selected_uids:
        raise ValueError("No currently restorable checkpoint matched that description.")
    projected = {entry.uid: entry for entry in checkpoint_picker_entries(entries)}
    options = [projected[uid] for uid in selected_uids if uid is not None]
    catalog = freeze_checkpoint_catalog(store)

    def revert_review_factory(uid: str, selected_keep: bool):
        unit = catalog.resolve(uid, context_name=name)
        return revert_exact_command_review(
            context_name=name,
            checkpoint_uid=uid,
            keep_history=selected_keep,
            affected_checkpoints=tuple(
                (member.context_name, member.checkpoint_uid) for member in unit.members
            ),
        )

    return choose_history(
        options,
        context_name=name,
        mode="revert",
        detail_renderer=checkpoint_revision_detail_renderer(entries),
        keep_history=keep,
        revert_review_factory=revert_review_factory,
    )


def _picker_selection(
    name: str,
    entries: list[dict[str, Any]],
    *,
    keep: bool,
) -> HistorySelectionReceipt | None:
    if not _interactive_terminal():
        raise ValueError(
            "Interactive checkpoint selection requires a terminal. "
            "Pass a checkpoint UID explicitly."
        )
    return choose_history(
        checkpoint_picker_entries(entries),
        context_name=name,
        mode="revert",
        detail_renderer=checkpoint_revision_detail_renderer(entries),
        keep_history=keep,
    )


def _validate_reviewed_frame(
    store: MemoryStore,
    *,
    context_name: str,
    context_uid: str,
    context_digest: str,
    history_digest: str,
    receipt: HistorySelectionReceipt,
) -> str:
    """Recheck the reviewed frame before entering the store's revert lock."""
    if receipt.context_name != context_name:
        raise ValueError(
            "The selected Context changed while history selection was open."
        )
    current = store.load_direct(context_name)
    if (
        current.uid != context_uid
        or context_record_digest(current) != context_digest
        or checkpoint_history_digest(store.list_checkpoints(context_name))
        != history_digest
    ):
        raise ValueError(
            "The Context or checkpoint history changed while selection was "
            "open. Review it again."
        )
    matching = _matching_checkpoint(
        store.list_checkpoints(context_name),
        receipt.checkpoint_uid,
    )
    if matching is None or matching.get("uid") != receipt.checkpoint_uid:
        raise ValueError("The selected checkpoint changed while selection was open.")
    return receipt.checkpoint_uid


def _resolved_memory_ref_contents(
    store: MemoryStore,
    *snapshots: object,
) -> dict[MemoryRefTargetKey, str | None]:
    """Resolve only the direct Source Memories named by receipt relationships.

    Revert checkpoints retain live Embed identity rather than Source bytes.
    Resolve those exact targets after the mutation so the receipt matches the
    list view without turning a failed optional display read into a failed
    mutation receipt.
    """

    result: dict[MemoryRefTargetKey, str | None] = {}
    for snapshot in snapshots:
        if not isinstance(snapshot, Mapping):
            continue
        items = snapshot.get("memories")
        if not isinstance(items, Mapping):
            continue
        for item in items.values():
            if not isinstance(item, Mapping) or item.get("type") not in {
                "memory_ref",
                "memory_snapshot_ref",
                "granted_memory_ref",
            }:
                continue
            key = memory_ref_target_key(item)
            if key is None or key in result:
                continue
            if item.get("type") == "memory_snapshot_ref":
                content = item.get("content")
                result[key] = content if isinstance(content, str) else None
                continue
            if item.get("type") == "granted_memory_ref":
                # The raw checkpoint intentionally carries no Source bytes,
                # and a local store lookup cannot authorize an external Grant.
                result[key] = None
                continue
            target_name, target_context_uid, target_memory_uid = key
            try:
                source = store.load_direct(target_name)
            except (FileNotFoundError, OSError, ValueError):
                result[key] = None
                continue
            target = source.memories.get(target_memory_uid)
            result[key] = (
                target.content
                if source.uid == target_context_uid and isinstance(target, Memory)
                else None
            )
    return result


def _apply_revert(
    store: MemoryStore,
    name: str,
    uid: str,
    *,
    keep: bool,
    expected_context_uid: str | None = None,
    expected_context_digest: str | None = None,
    expected_history_digest: str | None = None,
) -> None:
    try:
        pre_checkpoint, target = store.revert(
            name,
            uid,
            keep_history=keep,
            expected_context_uid=expected_context_uid,
            expected_context_digest=expected_context_digest,
            expected_history_digest=expected_history_digest,
        )
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    render_revert_receipt(
        context_name=name,
        before_snapshot=pre_checkpoint.snapshot,
        target=target,
        recovery=pre_checkpoint,
        resolved_memory_ref_contents=_resolved_memory_ref_contents(
            store,
            pre_checkpoint.snapshot,
            target.snapshot,
        ),
    )


def _apply_resolved_checkpoint_unit(
    store: MemoryStore,
    unit: ResolvedCheckpointUnit,
    *,
    keep: bool,
) -> None:
    """Apply one globally resolved direct or recursive recovery unit."""

    if not unit.is_recursive_set:
        member = unit.members[0]
        _apply_revert(
            store,
            member.context_name,
            member.checkpoint_uid,
            keep=keep,
            expected_context_uid=member.context_uid,
            expected_context_digest=member.expected_context_digest,
            expected_history_digest=member.expected_history_digest,
        )
        return
    try:
        result = store.revert_checkpoint_unit(unit, keep_history=keep)
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    resolved_by_context = {
        member.context_name: _resolved_memory_ref_contents(
            store,
            member.recovery.snapshot,
            member.target.snapshot,
        )
        for member in result.members
    }
    render_checkpoint_unit_revert_receipt(
        result,
        resolved_memory_ref_contents=resolved_by_context,
    )


def cmd(
    selector: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Globally resolved checkpoint UID/prefix, or a natural-language "
                "description; omit to inspect the current Context's history"
            )
        ),
    ] = None,
    keep: Annotated[
        bool,
        typer.Option(
            "--keep/--discard-newer",
            "-k",
            help=(
                "Keep newer checkpoints in the active log (default), or "
                "explicitly remove them with --discard-newer"
            ),
        ),
    ] = True,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help=(
                "Exact checkpoint location for interactive or semantic selection; "
                "an explicit UID otherwise prefers the command-start current "
                "location and falls back to the global checkpoint catalog"
            ),
        ),
    ] = None,
) -> None:
    store = MemoryStore()
    try:
        context_snapshot = ContextOperandSnapshot.capture(store)
        explicit_name = (
            context_snapshot.resolve(context_name) if context_name is not None else None
        )
        name = explicit_name or context_snapshot.current_name
    except ValueError as error:
        typer.secho(f"Context error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if selector is not None:
        selector = selector.strip()
        if not selector:
            typer.secho(
                "Error: checkpoint selector must be non-empty.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if _looks_like_missing_uid(selector):
            try:
                catalog = freeze_checkpoint_catalog(store)
                if explicit_name is not None:
                    unit = catalog.resolve(selector, context_name=explicit_name)
                elif name is not None:
                    try:
                        # Preserve inherited-Branch behavior by preferring the
                        # command-start current Context when it contains this
                        # UID. Fall back to the global direct owner only when
                        # the current location has no matching checkpoint.
                        unit = catalog.resolve(selector, context_name=name)
                    except CheckpointNotFoundError:
                        unit = catalog.resolve(selector)
                else:
                    unit = catalog.resolve(selector)
            except CheckpointCatalogError as error:
                typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
                raise typer.Exit(1)
            _apply_resolved_checkpoint_unit(store, unit, keep=keep)
            return

    if not name:
        typer.secho(
            "No current context. Run 'mem init <name>' first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if selector is None and _interactive_terminal():
        try:
            reviewed = browse_checkpoint_locations(
                store,
                session=None,
                context_locator=name,
                title="REVERT",
                mode="revert",
                keep_history=keep,
            )
        except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
            typer.secho(
                f"Revert picker error: {error}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if reviewed is None:
            typer.echo("Revert cancelled.")
            return
        _apply_resolved_checkpoint_unit(
            store,
            reviewed.checkpoint_unit,
            keep=reviewed.keep_history,
        )
        return

    try:
        context = store.load_direct(name)
        entries = store.list_checkpoints(name)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    if not entries:
        typer.secho(
            f"Error: no checkpoints exist for '{name}'.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    expected_context_uid = context.uid
    expected_context_digest = context_record_digest(context)
    expected_history_digest = checkpoint_history_digest(entries)

    if selector is not None:
        try:
            exact = _matching_checkpoint(entries, selector)
        except ValueError as error:
            typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        if exact is not None:
            _apply_revert(
                store,
                name,
                exact["uid"],
                keep=keep,
                expected_context_uid=expected_context_uid,
                expected_context_digest=expected_context_digest,
                expected_history_digest=expected_history_digest,
            )
            return
        if _looks_like_missing_uid(selector):
            typer.secho(
                f"Error: no checkpoint with uid prefix '{selector}'.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)

    try:
        receipt = (
            _picker_selection(
                name,
                entries,
                keep=keep,
            )
            if selector is None
            else _semantic_selection(
                store,
                name,
                entries,
                selector,
                keep=keep,
            )
        )
        if receipt is None:
            typer.echo("Revert cancelled.")
            return
        uid = _validate_reviewed_frame(
            store,
            context_name=name,
            context_uid=expected_context_uid,
            context_digest=expected_context_digest,
            history_digest=expected_history_digest,
            receipt=receipt,
        )
    except (
        HistoryError,
        HistorySearchError,
        QueryProviderError,
        ValueError,
    ) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        unit = freeze_checkpoint_catalog(store).resolve(uid, context_name=name)
    except CheckpointCatalogError as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    _apply_resolved_checkpoint_unit(
        store,
        unit,
        keep=receipt.keep_history,
    )
