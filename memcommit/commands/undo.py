"""Undo the most recent distinct Context state with the checkpoint engine."""
from __future__ import annotations

from typing import Annotated, Any

import typer

from memcommit.store import (
    MemoryStore,
    canonical_context_record,
    checkpoint_history_digest,
    context_record_digest,
)


def _snapshot_for_context(
    snapshot: object,
    *,
    context_uid: str,
    context_name: str,
) -> dict[str, Any] | None:
    """Normalize inherited checkpoint identity before comparing its state."""
    if not isinstance(snapshot, dict):
        return None
    try:
        return canonical_context_record(
            {
                **snapshot,
                "uid": context_uid,
                "name": context_name,
            }
        )
    except (KeyError, TypeError, ValueError):
        return None


def _undo_target(
    store: MemoryStore,
    context_name: str,
) -> tuple[str, str, str, str]:
    """Return a target UID and the exact Context/history frame it came from."""
    context = store.load_direct(context_name)
    current = context.to_dict()
    entries = store.list_checkpoints(context_name)
    for entry in entries:
        candidate = _snapshot_for_context(
            entry.get("snapshot"),
            context_uid=context.uid,
            context_name=context.name,
        )
        if candidate is None:
            raise ValueError(
                "Checkpoint history contains an invalid snapshot."
            )
        # Manual checkpoints and no-op operations can repeat the same state.
        # Undo is state-oriented, so they are deliberately skipped.
        if candidate != current:
            uid = entry.get("uid")
            if not isinstance(uid, str) or not uid:
                raise ValueError(
                    "Checkpoint history contains an invalid UID."
                )
            return (
                uid,
                context.uid,
                context_record_digest(context),
                checkpoint_history_digest(entries),
            )
    raise ValueError(
        f"Context '{context_name}' has no earlier distinct state to undo to."
    )


def cmd(
    keep: Annotated[
        bool,
        typer.Option(
            "--keep",
            "-k",
            help="Keep newer checkpoints in the log instead of truncating",
        ),
    ] = False,
) -> None:
    """Restore the most recent saved Context state distinct from the live one."""
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
        (
            target_uid,
            expected_context_uid,
            expected_context_digest,
            expected_history_digest,
        ) = _undo_target(store, name)
        # Resolve the target and recheck the frame inside MemoryStore's write
        # lock. Selection and mutation therefore cannot straddle another save,
        # checkpoint, or revert.
        pre_checkpoint, target = store.revert(
            name,
            target_uid,
            keep_history=keep,
            expected_context_uid=expected_context_uid,
            expected_context_digest=expected_context_digest,
            expected_history_digest=expected_history_digest,
        )
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        typer.secho(f"Undo error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    target_ts = target.timestamp.strftime("%Y-%m-%d %H:%M")
    typer.secho(
        f"Undid the last Context state change to "
        f"[{target.uid[:8]}] ({target_ts}).",
        fg=typer.colors.GREEN,
    )
    typer.secho(
        f"Undo this undo with: mem revert {pre_checkpoint.uid[:8]}",
        dim=True,
    )
