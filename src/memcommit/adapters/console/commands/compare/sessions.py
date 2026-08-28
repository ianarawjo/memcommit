"""Discover exact saved Compare analyses for the shared session picker."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

from memcommit.application.operations.compare.ledger.model import ComparisonAnalysis
from memcommit.application.operations.compare.ledger.session_application import (
    iter_saved_comparisons,
    load_saved_comparison,
    revalidate_saved_comparison,
)
from memcommit.adapters.console.tui.components.operation_launcher.session import (
    SessionNewReceipt,
    SessionOpenReceipt,
    SessionPickerEntry,
    choose_session,
)
from memcommit.persistence.store import MemoryStore


def _created_timestamp(value: str) -> float:
    try:
        return datetime.fromisoformat(value).timestamp()
    except (TypeError, ValueError) as error:
        raise ValueError("Saved comparison analysis has an invalid timestamp.") from error


def _artifact_timestamp(analysis: ComparisonAnalysis, path: Path) -> float:
    timestamp = _created_timestamp(analysis.created_at)
    try:
        if path.is_file() and not path.is_symlink():
            timestamp = max(timestamp, path.stat().st_mtime)
    except FileNotFoundError:
        # A selected UID is reloaded after the picker, so a concurrent delete
        # here only removes a presentation timestamp from this frozen catalog.
        pass
    return timestamp


def comparison_session_entries(
    store: MemoryStore,
    *,
    ledger: bool = False,
) -> tuple[SessionPickerEntry, ...]:
    """Project saved Compare analyses as read-only viewer entries."""
    # Import lazily because compare.py owns command orchestration and imports
    # this picker adapter. The picker preview must nevertheless reuse the exact
    # compact renderer instead of maintaining a second summary shape.
    from memcommit.adapters.console.commands.compare.presentation import render_comparison

    entries: list[SessionPickerEntry] = []
    for analysis, path in iter_saved_comparisons(store):
        reference, compared = analysis.frames
        status = "CURRENT"
        try:
            revalidate_saved_comparison(store, analysis)
        except (FileNotFoundError, OSError, ValueError):
            status = "STALE"
        # Include both operands so this public route remains stable even when
        # the process-global current Context changes after picker discovery.
        argv = (
            "mem",
            "compare",
            reference.context_name,
            compared.context_name,
        )
        if ledger:
            argv += ("--ledger",)
        entries.append(
            SessionPickerEntry(
                kind="compare",
                key=analysis.uid,
                title=(
                    f"{reference.context_name} ↔ {compared.context_name}"
                ),
                status=status,
                subtitle=(
                    f"{len(analysis.relations)} relations · "
                    f"{len(analysis.issues)} potential conflicts"
                ),
                group=reference.context_name,
                sort_timestamp=_artifact_timestamp(analysis, path),
                detail=render_comparison(
                    analysis,
                    reused=True,
                    durable=True,
                ),
                reopen_argv=argv,
                detail_only=True,
            )
        )
    return tuple(entries)


def choose_comparison_session(
    store: MemoryStore,
    *,
    ledger: bool = False,
) -> SessionOpenReceipt | SessionNewReceipt | None:
    """Return an exact saved-analysis receipt; never run Compare."""
    entries = comparison_session_entries(store, ledger=ledger)
    # Non-interactive callers retain a stable empty result, while a terminal
    # deliberately opens the launcher even before the first analysis exists.
    if not entries and not (sys.stdin.isatty() and sys.stdout.isatty()):
        return None
    receipt = choose_session(
        entries,
        title="MEM COMPARE · SAVED ANALYSES",
        new_receipt=SessionNewReceipt(
            kind="compare",
            argv=("mem", "compare"),
        ),
    )
    if receipt is None:
        return None
    if isinstance(receipt, SessionNewReceipt):
        if receipt.kind != "compare" or receipt.argv != ("mem", "compare"):
            raise ValueError("Compare session picker returned an invalid receipt.")
        return receipt
    if not isinstance(receipt, SessionOpenReceipt) or receipt.kind != "compare":
        raise ValueError("Compare session picker returned an invalid receipt.")
    entry_by_key = {entry.key: entry for entry in entries}
    selected = entry_by_key.get(receipt.key)
    if selected is None or receipt.argv != selected.reopen_argv:
        raise ValueError("Compare session picker returned a forged receipt.")
    return receipt


__all__ = [
    "choose_comparison_session",
    "comparison_session_entries",
    "iter_saved_comparisons",
    "load_saved_comparison",
    "revalidate_saved_comparison",
]
