"""Discover exact saved Atomize analyses for the shared session picker."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import uuid

import memcommit.store as store_module
from memcommit.atomize import (
    ATOMIZE_RULESET_VERSION,
    AtomizeAnalysisSession,
    atomize_analysis_matches_context,
)
from memcommit.commands.session_picker import (
    SessionOpenReceipt,
    SessionPickerEntry,
    choose_session,
)
from memcommit.context import Context
from memcommit.review import direct_context_digest
from memcommit.store import MemoryStore


_FINAL_ANALYSIS_NAME = re.compile(r"^([0-9a-f-]{36})\.json$")
_ATOMIC_TEMP_NAME = re.compile(
    r"^\.([0-9a-f-]{36})\.json\.write-([0-9a-f]{32})$"
)


def _canonical_uuid(value: str, label: str) -> str:
    try:
        canonical = str(uuid.UUID(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid {label}.") from error
    if canonical != value:
        raise ValueError(f"Invalid {label}.")
    return canonical


def _created_timestamp(value: str) -> float:
    try:
        return datetime.fromisoformat(value).timestamp()
    except (TypeError, ValueError) as error:
        raise ValueError("Saved atomize analysis has an invalid timestamp.") from error


def _artifact_timestamp(
    store: MemoryStore,
    analysis: AtomizeAnalysisSession,
    analysis_path: Path,
) -> float:
    """Use the latest durable Atomize interaction, not discovery time."""
    timestamp = _created_timestamp(analysis.created_at)
    paths = (
        analysis_path,
        store._atomize_workbench_path(analysis.context_uid),
        store._atomize_grounding_session_path(analysis.context_uid),
    )
    for path in paths:
        try:
            if path.is_file() and not path.is_symlink():
                timestamp = max(timestamp, path.stat().st_mtime)
        except FileNotFoundError:
            # Atomic replacement can move a presentation timestamp between
            # discovery and stat. The persisted semantic timestamp remains a
            # deterministic fallback; selection revalidates the artifact.
            continue
    return timestamp


def _analysis_files() -> tuple[tuple[str, Path], ...]:
    root = store_module.ATOMIZE_ANALYSES_DIR
    if not root.exists():
        return ()
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Atomize analysis storage is invalid.")
    records: list[tuple[str, Path]] = []
    for path in root.iterdir():
        if path.is_symlink() or not path.is_file():
            raise ValueError("Atomize analysis storage is invalid.")
        if _ATOMIC_TEMP_NAME.fullmatch(path.name) is not None:
            # A concurrent atomic writer has not made this record durable yet.
            continue
        match = _FINAL_ANALYSIS_NAME.fullmatch(path.name)
        if match is None:
            raise ValueError("Atomize analysis storage is invalid.")
        context_uid = _canonical_uuid(
            match.group(1),
            "atomize analysis Context uid",
        )
        records.append((context_uid, path))
    return tuple(sorted(records, key=lambda record: record[0]))


def iter_saved_atomize_analyses(
    store: MemoryStore,
) -> tuple[tuple[AtomizeAnalysisSession, Path], ...]:
    """Strictly load every latest Context-scoped Atomize analysis."""
    records: list[tuple[AtomizeAnalysisSession, Path]] = []
    for context_uid, path in _analysis_files():
        analysis = store.load_atomize_analysis(context_uid)
        if analysis is None:
            # The exact file may have been removed after enumeration. It is
            # not selectable; a later explicit UID lookup will also fail.
            continue
        records.append((analysis, path))
    return tuple(records)


def load_saved_atomize_analysis(
    store: MemoryStore,
    analysis_uid: str,
) -> AtomizeAnalysisSession:
    """Resolve one exact analysis UID without falling into create/refresh."""
    expected_uid = _canonical_uuid(analysis_uid, "atomize analysis uid")
    matches = [
        analysis
        for analysis, _path in iter_saved_atomize_analyses(store)
        if analysis.uid == expected_uid
    ]
    if not matches:
        raise ValueError(
            f"Saved atomize analysis '{analysis_uid}' is no longer available."
        )
    if len(matches) != 1:
        raise ValueError("Saved atomize analysis identity is not unique.")
    return matches[0]


def revalidate_saved_atomize_analysis(
    store: MemoryStore,
    analysis: AtomizeAnalysisSession,
) -> tuple[Context, bool]:
    """Return the current Context and whether this exact plan was applied."""
    if analysis.ruleset_version != ATOMIZE_RULESET_VERSION:
        raise ValueError(
            "This atomize analysis uses an older semantic ruleset. Run "
            "'mem impact atomize --refresh' for its source Context before "
            "reopening it."
        )
    try:
        context = store.load_direct(analysis.context_name)
    except FileNotFoundError as error:
        raise ValueError(
            "The source Context for this saved atomize analysis no longer "
            "exists."
        ) from error
    if context.uid != analysis.context_uid or context.name != analysis.context_name:
        raise ValueError(
            "The source Context identity changed after this atomize analysis "
            "was saved."
        )
    if atomize_analysis_matches_context(analysis, context):
        return context, False
    if atomize_analysis_was_applied(store, context, analysis.uid):
        return context, True
    else:
        raise ValueError(
            "The source Context changed after this atomize analysis was "
            "saved. Refresh it explicitly before reopening current work."
        )


def atomize_analysis_was_applied(
    store: MemoryStore,
    context: Context,
    analysis_uid: str,
) -> bool:
    """Recognize the exact current post-application state provider-free."""
    current_digest = direct_context_digest(context)
    for checkpoint in store.list_checkpoints(context.name):
        args = checkpoint.get("args")
        trace = args.get("trace") if isinstance(args, dict) else None
        if not (
            isinstance(trace, dict)
            and trace.get("operation_id") == analysis_uid
        ):
            continue
        snapshot = checkpoint.get("snapshot")
        if not isinstance(snapshot, dict):
            continue
        try:
            checkpoint_context = Context.from_dict(snapshot)
        except (KeyError, TypeError):
            continue
        if (
            checkpoint_context.uid == context.uid
            and checkpoint_context.name == context.name
            and direct_context_digest(checkpoint_context) == current_digest
        ):
            return True
    return False


def atomize_session_entries(
    store: MemoryStore,
    *,
    show_all: bool = False,
) -> tuple[SessionPickerEntry, ...]:
    """Project saved Atomize artifacts without rendering source Memory text."""
    entries: list[SessionPickerEntry] = []
    for analysis, path in iter_saved_atomize_analyses(store):
        status = "CURRENT"
        applied = False
        try:
            _context, applied = revalidate_saved_atomize_analysis(store, analysis)
        except (FileNotFoundError, OSError, ValueError):
            status = "STALE"
        workbench = store.load_atomize_workbench(analysis)
        grounding = store.load_atomize_grounding_session(analysis.context_uid)
        if status == "CURRENT" and applied:
            status = "APPLIED"
        elif status == "CURRENT" and grounding is not None and grounding.state in {
            "AWAITING_REPLY",
            "READY_TO_APPLY",
        }:
            status = grounding.state
        elif status == "CURRENT" and workbench is None:
            status = "ANALYSIS ONLY"
        issue_count = len(workbench.issues) if workbench is not None else 0
        argv = ("mem", "atomize", "--context", analysis.context_name)
        if show_all:
            argv += ("--all",)
        entries.append(
            SessionPickerEntry(
                kind="atomize",
                key=analysis.uid,
                title=analysis.context_name,
                status=status,
                subtitle=(
                    f"{analysis.memory_count} → "
                    f"{analysis.projected_memory_count} Memories · "
                    f"{issue_count} issues"
                ),
                group=analysis.context_name,
                sort_timestamp=_artifact_timestamp(
                    store,
                    analysis,
                    path,
                ),
                detail=(
                    f"Analysis {analysis.uid}\n"
                    f"Source Context {analysis.context_name} "
                    f"[{analysis.context_uid}]\n"
                    "Picker selection uses the frozen analysis UID and "
                    "revalidates it without provider or refresh. The shown "
                    "argv is only the nearest public route and is not "
                    "executed by the picker."
                ),
                reopen_argv=argv,
            )
        )
    return tuple(entries)


def choose_atomize_session(
    store: MemoryStore,
    *,
    show_all: bool = False,
) -> SessionOpenReceipt | None:
    """Return an exact picker receipt; never create Atomize work."""
    entries = atomize_session_entries(store, show_all=show_all)
    if not entries:
        return None
    receipt = choose_session(
        entries,
        title="MEM ATOMIZE · SAVED ANALYSES",
    )
    if receipt is None:
        return None
    if not isinstance(receipt, SessionOpenReceipt) or receipt.kind != "atomize":
        raise ValueError("Atomize session picker returned an invalid receipt.")
    entry_by_key = {entry.key: entry for entry in entries}
    selected = entry_by_key.get(receipt.key)
    if selected is None or receipt.argv != selected.reopen_argv:
        raise ValueError("Atomize session picker returned a forged receipt.")
    return receipt
