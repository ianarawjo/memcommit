"""Persistence for latest ordered peer-comparison analyses."""
from __future__ import annotations

from contextlib import ExitStack
import json
from pathlib import Path
import re
import uuid

import memcommit.store as store_module
from memcommit.comparison import (
    ComparisonAnalysis,
    ComparisonError,
)


class ConcurrentComparisonUpdateError(RuntimeError):
    """A source or ordered comparison slot changed during analysis."""


_FINAL_ANALYSIS_NAME = re.compile(
    r"^([0-9a-f-]{36})--([0-9a-f-]{36})\.json$"
)
_ATOMIC_TEMP_NAME = re.compile(
    r"^\.([0-9a-f-]{36})--([0-9a-f-]{36})"
    r"\.json\.write-([0-9a-f]{32})$"
)


def comparison_analyses_dir() -> Path:
    """Resolve against the store root at call time for isolated tests."""
    return store_module.STORE_DIR / "comparison-analyses"


def _canonical_uuid(value: str, label: str) -> str:
    try:
        canonical = str(uuid.UUID(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid {label}.") from error
    if canonical != value:
        raise ValueError(f"Invalid {label}.")
    return canonical


def comparison_analysis_path(
    reference_context_uid: str,
    compared_context_uid: str,
) -> Path:
    reference = _canonical_uuid(
        reference_context_uid,
        "comparison reference Context uid",
    )
    compared = _canonical_uuid(
        compared_context_uid,
        "comparison compared Context uid",
    )
    if reference == compared:
        raise ValueError(
            "Comparison analysis requires distinct Context uids."
        )
    root = comparison_analyses_dir()
    if root.is_symlink():
        raise ValueError(
            "Comparison analysis storage cannot be a symbolic link."
        )
    if root.exists() and not root.is_dir():
        raise ValueError("Comparison analysis storage is invalid.")
    return root / f"{reference}--{compared}.json"


def _strict_json_object(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load_comparison_analysis(
    reference_context_uid: str,
    compared_context_uid: str,
) -> ComparisonAnalysis | None:
    """Load one ordered latest slot without creating store state."""
    path = comparison_analysis_path(
        reference_context_uid,
        compared_context_uid,
    )
    if not path.exists():
        return None
    if not path.is_file() or path.is_symlink():
        raise ValueError("Comparison analysis storage is invalid.")
    try:
        with open(path, encoding="utf-8") as file:
            value = json.load(
                file,
                object_pairs_hook=_strict_json_object,
            )
        analysis = ComparisonAnalysis.from_dict(value)
    except (
        ComparisonError,
        json.JSONDecodeError,
        ValueError,
    ) as error:
        raise ValueError("Saved comparison analysis is invalid.") from error
    if (
        analysis.frames[0].context_uid != reference_context_uid
        or analysis.frames[1].context_uid != compared_context_uid
    ):
        raise ValueError(
            "Saved comparison analysis does not match its ordered storage "
            "key."
        )
    return analysis


def save_comparison_analysis(
    store: store_module.MemoryStore,
    analysis: ComparisonAnalysis,
    *,
    expected_analysis_uid: str | None,
) -> None:
    """CAS-save one analysis while both exact source Contexts stay locked."""
    if not isinstance(store, store_module.MemoryStore):
        raise TypeError("Expected a MemoryStore.")
    if not isinstance(analysis, ComparisonAnalysis):
        raise TypeError("Expected a ComparisonAnalysis.")
    restored = ComparisonAnalysis.from_dict(analysis.to_dict())
    if restored.uid != analysis.uid:
        raise ValueError("Comparison analysis identity changed during save.")
    if expected_analysis_uid is not None:
        _canonical_uuid(
            expected_analysis_uid,
            "expected comparison analysis uid",
        )

    reference_frame, compared_frame = analysis.frames
    path = comparison_analysis_path(
        reference_frame.context_uid,
        compared_frame.context_uid,
    )
    # Context locks are sufficient as the ordered pair's cooperative slot
    # lock because every writer for this pair must hold the same two locks.
    # The slot UID CAS then prevents a slower provider call from replacing a
    # newer analysis of the same unchanged pair.
    with ExitStack() as locks:
        for name in sorted(
            {
                reference_frame.context_name,
                compared_frame.context_name,
            }
        ):
            locks.enter_context(store._context_write_lock(name))
        locks.enter_context(store.profile_write_guard())

        try:
            reference = store.load_direct(reference_frame.context_name)
            compared = store.load_direct(compared_frame.context_name)
        except FileNotFoundError as error:
            raise ConcurrentComparisonUpdateError(
                "A comparison source Context no longer exists."
            ) from error
        if not analysis.matches(reference, compared):
            raise ConcurrentComparisonUpdateError(
                "A source Context changed while Compare was analyzing it; "
                "the new analysis was not saved."
            )

        current = load_comparison_analysis(
            reference_frame.context_uid,
            compared_frame.context_uid,
        )
        current_uid = current.uid if current is not None else None
        if current_uid != expected_analysis_uid:
            raise ConcurrentComparisonUpdateError(
                "The ordered comparison slot changed before this analysis "
                "could be saved."
            )

        root = comparison_analyses_dir()
        if root.exists() and (
            not root.is_dir() or root.is_symlink()
        ):
            raise ValueError("Comparison analysis storage is invalid.")
        root.mkdir(parents=True, exist_ok=True)
        if path.exists() and (not path.is_file() or path.is_symlink()):
            raise ValueError("Comparison analysis storage is invalid.")
        store_module._write_json_atomic(path, analysis.to_dict())


def comparison_paths_for_context(context_uid: str) -> tuple[Path, ...]:
    """Preflight and return ordered-pair artifacts containing one Context."""
    canonical = _canonical_uuid(
        context_uid,
        "comparison source Context uid",
    )
    root = comparison_analyses_dir()
    if not root.exists():
        return ()
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Comparison analysis storage is invalid.")
    matches: list[Path] = []
    for path in root.iterdir():
        if path.is_symlink() or not path.is_file():
            raise ValueError("Comparison analysis storage is invalid.")
        match = _FINAL_ANALYSIS_NAME.fullmatch(path.name)
        if match is None:
            match = _ATOMIC_TEMP_NAME.fullmatch(path.name)
        if match is None:
            raise ValueError("Comparison analysis storage is invalid.")
        reference = _canonical_uuid(
            match.group(1),
            "stored comparison reference Context uid",
        )
        compared = _canonical_uuid(
            match.group(2),
            "stored comparison compared Context uid",
        )
        if canonical in {reference, compared}:
            matches.append(path)
    return tuple(sorted(matches))


def delete_comparison_paths(paths: tuple[Path, ...]) -> None:
    """Delete an exact preflighted set and prune an empty analysis root."""
    root = comparison_analyses_dir()
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError("Comparison analysis storage is invalid.")
    for path in paths:
        if path.parent != root or path.is_symlink():
            raise ValueError("Comparison analysis storage changed during delete.")
        if not path.exists():
            # Concurrent deletion of the other bound source can already have
            # removed this exact pair artifact. Missing is the desired final
            # privacy state, not a reason to report that primary deletion
            # failed after it already committed.
            continue
        if not path.is_file():
            raise ValueError("Comparison analysis storage changed during delete.")
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    if root.exists():
        try:
            root.rmdir()
        except OSError:
            pass
