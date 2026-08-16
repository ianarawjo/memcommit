"""Discover exact saved Compare analyses for the shared session picker."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import sys
import uuid

from memcommit.comparison import (
    COMPARISON_RULESET_VERSION,
    ComparisonAnalysis,
)
from memcommit.comparison_store import (
    comparison_analyses_dir,
    load_comparison_analysis,
)
from memcommit.commands.session_picker import (
    SessionNewReceipt,
    SessionOpenReceipt,
    SessionPickerEntry,
    choose_session,
)
from memcommit.granted_comparison_store import (
    granted_artifact_contexts,
    iter_granted_comparison_artifacts,
)
from memcommit.store import MemoryStore


_FINAL_ANALYSIS_NAME = re.compile(
    r"^([0-9a-f-]{36})--([0-9a-f-]{36})\.json$"
)
_ATOMIC_TEMP_NAME = re.compile(
    r"^\.([0-9a-f-]{36})--([0-9a-f-]{36})"
    r"\.json\.write-([0-9a-f]{32})$"
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


def iter_saved_comparisons(
    store: MemoryStore | None = None,
) -> tuple[tuple[ComparisonAnalysis, Path], ...]:
    """Strictly load ordinary and visible granted latest-pair analyses."""
    root = comparison_analyses_dir()
    records: list[tuple[ComparisonAnalysis, Path]] = []
    if root.exists():
        if not root.is_dir() or root.is_symlink():
            raise ValueError("Comparison analysis storage is invalid.")
        for path in root.iterdir():
            if path.is_symlink() or not path.is_file():
                raise ValueError("Comparison analysis storage is invalid.")
            if _ATOMIC_TEMP_NAME.fullmatch(path.name) is not None:
                continue
            match = _FINAL_ANALYSIS_NAME.fullmatch(path.name)
            if match is None:
                raise ValueError("Comparison analysis storage is invalid.")
            reference_uid = _canonical_uuid(
                match.group(1),
                "comparison reference Context uid",
            )
            compared_uid = _canonical_uuid(
                match.group(2),
                "comparison compared Context uid",
            )
            analysis = load_comparison_analysis(reference_uid, compared_uid)
            if analysis is not None:
                records.append((analysis, path))
    if store is not None:
        records.extend(
            (artifact.analysis, path)
            for artifact, path in iter_granted_comparison_artifacts(store)
        )
    return tuple(sorted(records, key=lambda record: record[0].uid))


def load_saved_comparison(
    analysis_uid: str,
    *,
    store: MemoryStore | None = None,
) -> ComparisonAnalysis:
    """Resolve an exact analysis UID without selecting or refreshing a pair."""
    expected_uid = _canonical_uuid(analysis_uid, "comparison analysis uid")
    matches = [
        analysis
        for analysis, _path in iter_saved_comparisons(store)
        if analysis.uid == expected_uid
    ]
    if not matches:
        raise ValueError(
            f"Saved comparison analysis '{analysis_uid}' is no longer available."
        )
    if len(matches) != 1:
        raise ValueError("Saved comparison analysis identity is not unique.")
    return matches[0]


def revalidate_saved_comparison(
    store: MemoryStore,
    analysis: ComparisonAnalysis,
) -> None:
    """Fail closed if either exact source no longer matches the analysis."""
    granted = next(
        (
            artifact
            for artifact, _path in iter_granted_comparison_artifacts(store)
            if artifact.analysis.uid == analysis.uid
        ),
        None,
    )
    if granted is not None:
        reference, compared = granted_artifact_contexts(store, granted)
        if not analysis.matches(reference, compared):
            raise ValueError(
                "A granted source changed after this comparison was saved."
            )
        if analysis.ruleset_version != COMPARISON_RULESET_VERSION:
            raise ValueError(
                "This comparison uses an older semantic ruleset. Refresh the "
                "explicit ordered pair before reopening it as current analysis."
            )
        return
    reference_frame, compared_frame = analysis.frames
    try:
        reference = store.load_direct(reference_frame.context_name)
        compared = store.load_direct(compared_frame.context_name)
    except FileNotFoundError as error:
        raise ValueError(
            "A source Context for this saved comparison no longer exists."
        ) from error
    if not analysis.matches(reference, compared):
        raise ValueError(
            "A source Context changed after this comparison was saved. Run "
            "an explicit 'mem compare --refresh --to CONTEXT' before using "
            "it as current analysis."
        )
    if analysis.ruleset_version != COMPARISON_RULESET_VERSION:
        raise ValueError(
            "This comparison uses an older semantic ruleset. Refresh the "
            "explicit ordered pair before reopening it as current analysis."
        )


def comparison_session_entries(
    store: MemoryStore,
    *,
    ledger: bool = False,
) -> tuple[SessionPickerEntry, ...]:
    """Project saved Compare analyses as read-only viewer entries."""
    # Import lazily because compare.py owns command orchestration and imports
    # this picker adapter. The picker preview must nevertheless reuse the exact
    # compact renderer instead of maintaining a second summary shape.
    from memcommit.comparison_present import render_comparison

    entries: list[SessionPickerEntry] = []
    for analysis, path in iter_saved_comparisons(store):
        reference, compared = analysis.frames
        status = "CURRENT"
        try:
            revalidate_saved_comparison(store, analysis)
        except (FileNotFoundError, OSError, ValueError):
            status = "STALE"
        argv = ("mem", "compare", "--to", compared.context_name)
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
