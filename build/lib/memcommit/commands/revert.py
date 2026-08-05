"""Restore one exact checkpoint, optionally selected through history search."""
from __future__ import annotations

import json
import re
import sys
from typing import Annotated, Any, Optional

import typer

from memcommit.commands.history_picker import (
    HistorySelectionReceipt,
    choose_history,
)
from memcommit.commands.history_present import checkpoint_picker_entries
from memcommit.commands.restoration_present import render_revert_receipt
from memcommit.history import HistoryError, build_history
from memcommit.history_search import HistorySearchError, search_history
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.store import (
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
        if isinstance(entry.get("uid"), str)
        and entry["uid"].startswith(selector)
    ]
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous prefix '{selector}' matches "
            f"{len(matches)} checkpoints."
        )
    return matches[0] if matches else None


def _looks_like_missing_uid(selector: str) -> bool:
    return (
        _UID_LIKE.fullmatch(selector) is not None
        and sum(character != "-" for character in selector) >= 8
    )


def _revert_preview(
    entries: list[dict[str, Any]],
    *,
    keep: bool,
) -> dict[str, str]:
    details: dict[str, str] = {}
    for index, entry in enumerate(entries):
        uid = entry.get("uid")
        if not isinstance(uid, str):
            continue
        if keep:
            line = (
                "Revert log: --keep preserves every currently visible "
                "checkpoint."
            )
        else:
            line = (
                f"Revert log: {index} newer visible checkpoint"
                f"{'s' if index != 1 else ''} may leave the active log; "
                "the pre-revert recovery checkpoint retains undo metadata."
            )
        details[uid] = line
    return details


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
    results = search_history(
        timeline,
        query,
        connect_codex_chatgpt_provider(),
        result_kinds=("checkpoint",),
        limit=20,
    )
    active_uids = {
        entry["uid"]
        for entry in entries
        if isinstance(entry.get("uid"), str)
    }
    selected_uids = [
        result.checkpoint_uid
        for result in results
        if result.selectable and result.checkpoint_uid in active_uids
    ]
    if not selected_uids:
        raise ValueError(
            "No currently restorable checkpoint matched that description."
        )
    projected = {
        entry.uid: entry
        for entry in checkpoint_picker_entries(
            entries,
            extra_detail_by_uid=_revert_preview(entries, keep=keep),
        )
    }
    options = [
        projected[uid]
        for uid in selected_uids
        if uid is not None
    ]
    return choose_history(
        options,
        context_name=name,
        mode="revert",
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
        checkpoint_picker_entries(
            entries,
            extra_detail_by_uid=_revert_preview(entries, keep=keep),
        ),
        context_name=name,
        mode="revert",
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
    if (
        receipt.context_name != context_name
        or store.current_context_name() != context_name
    ):
        raise ValueError(
            "The current Context changed while history selection was open."
        )
    current = store.load_direct(context_name)
    if (
        current.uid != context_uid
        or context_record_digest(current) != context_digest
        or checkpoint_history_digest(
            store.list_checkpoints(context_name)
        )
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
    if (
        matching is None
        or matching.get("uid") != receipt.checkpoint_uid
    ):
        raise ValueError(
            "The selected checkpoint changed while selection was open."
        )
    return receipt.checkpoint_uid


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
    )


def cmd(
    selector: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Checkpoint UID/prefix, or a natural-language description; "
                "omit to choose interactively"
            )
        ),
    ] = None,
    keep: Annotated[
        bool,
        typer.Option(
            "--keep",
            "-k",
            help="Keep newer checkpoints in the log instead of truncating",
        ),
    ] = False,
) -> None:
    store = MemoryStore()
    name = store.current_context_name()
    if not name:
        typer.secho(
            "No current context. Run 'mem init <name>' first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

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

    if selector is not None:
        selector = selector.strip()
        if not selector:
            typer.secho(
                "Error: checkpoint selector must be non-empty.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        try:
            exact = _matching_checkpoint(entries, selector)
        except ValueError as error:
            typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        if exact is not None:
            _apply_revert(store, name, exact["uid"], keep=keep)
            return
        if _looks_like_missing_uid(selector):
            typer.secho(
                f"Error: no checkpoint with uid prefix '{selector}'.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)

    expected_context_uid = context.uid
    expected_context_digest = context_record_digest(context)
    expected_history_digest = checkpoint_history_digest(entries)
    try:
        receipt = (
            _picker_selection(name, entries, keep=keep)
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

    _apply_revert(
        store,
        name,
        uid,
        keep=keep,
        expected_context_uid=expected_context_uid,
        expected_context_digest=expected_context_digest,
        expected_history_digest=expected_history_digest,
    )
