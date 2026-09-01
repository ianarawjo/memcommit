"""Terminal-independent lifecycle for durable read-only Compare analyses."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import uuid

from memcommit.application.capabilities.memory_issue_analysis.peer_relations.model import (
    COMPARISON_RULESET_VERSION,
    ComparisonAnalysis,
    comparison_canonical_digest,
)
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.execution import (
    load_comparison_context,
)
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.repository import (
    comparison_analyses_dir,
    load_comparison_analysis,
)
from memcommit.application.context_access.access import ContextAccess
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.granted_repository import (
    granted_artifact_contexts,
    iter_granted_comparison_artifacts,
)
from memcommit.persistence.store import MemoryStore


_FINAL_ANALYSIS_NAME = re.compile(
    r"^([0-9a-f-]{36})--([0-9a-f-]{36})\.json$"
)
_ATOMIC_TEMP_NAME = re.compile(
    r"^\.([0-9a-f-]{36})--([0-9a-f-]{36})"
    r"\.json\.write-([0-9a-f]{32})$"
)


class ComparisonSessionInputError(ValueError):
    """A saved Compare locator or version has invalid syntax."""


class ComparisonSessionUnavailableError(ValueError):
    """An exact durable Compare analysis is not available."""


class ComparisonSessionConflictError(ValueError):
    """A saved Compare analysis or one of its sources changed."""


@dataclass(frozen=True)
class ComparisonSessionSnapshot:
    """One exact durable Compare analysis and its opaque content version."""

    analysis: ComparisonAnalysis
    version_token: str


def _canonical_uuid(value: str, label: str) -> str:
    try:
        canonical = str(uuid.UUID(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ComparisonSessionInputError(f"Invalid {label}.") from error
    if canonical != value:
        raise ComparisonSessionInputError(f"Invalid {label}.")
    return canonical


def _version(value: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ComparisonSessionInputError(
            "Compare refresh requires a valid opaque saved version."
        )
    return value


def iter_saved_comparisons(
    store: MemoryStore,
) -> tuple[tuple[ComparisonAnalysis, Path], ...]:
    """Strictly load ordinary and visible granted latest-pair analyses."""

    if not isinstance(store, MemoryStore):
        raise TypeError("Compare session discovery requires a MemoryStore.")
    root = comparison_analyses_dir(store)
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
            analysis = load_comparison_analysis(
                reference_uid,
                compared_uid,
                store=store,
            )
            if analysis is not None:
                records.append((analysis, path))
    records.extend(
        (artifact.analysis, path)
        for artifact, path in iter_granted_comparison_artifacts(store)
    )
    return tuple(sorted(records, key=lambda record: record[0].uid))


def load_saved_comparison(
    analysis_uid: str,
    *,
    store: MemoryStore,
) -> ComparisonAnalysis:
    """Resolve an exact latest-slot analysis UID without refreshing its pair."""

    expected_uid = _canonical_uuid(analysis_uid, "comparison analysis uid")
    matches = [
        analysis
        for analysis, _path in iter_saved_comparisons(store)
        if analysis.uid == expected_uid
    ]
    if not matches:
        raise ComparisonSessionUnavailableError(
            f"Saved comparison analysis '{analysis_uid}' is no longer available."
        )
    if len(matches) != 1:
        raise ComparisonSessionUnavailableError(
            "Saved comparison analysis identity is not unique."
        )
    return matches[0]


def revalidate_saved_comparison(
    store: MemoryStore,
    analysis: ComparisonAnalysis,
) -> None:
    """Fail closed unless the exact saved sources and ruleset remain current."""

    granted = next(
        (
            artifact
            for artifact, _path in iter_granted_comparison_artifacts(store)
            if artifact.analysis.uid == analysis.uid
        ),
        None,
    )
    if granted is not None:
        try:
            reference, compared = granted_artifact_contexts(store, granted)
        except (FileNotFoundError, OSError, ValueError) as error:
            raise ComparisonSessionConflictError(str(error)) from error
    else:
        contexts = []
        try:
            for frame, include_descendants in zip(
                analysis.frames,
                analysis.include_descendants,
                strict=True,
            ):
                contexts.append(
                    load_comparison_context(
                        ContextAccess(
                            store=store,
                            context_name=frame.context_name,
                            access_name=frame.context_name,
                            permission="READ",
                        ),
                        include_descendants=include_descendants,
                    )
                )
        except FileNotFoundError as error:
            raise ComparisonSessionConflictError(
                "A source Context for this saved comparison no longer exists."
            ) from error
        reference, compared = contexts
    if not analysis.matches(reference, compared):
        raise ComparisonSessionConflictError(
            "A source Context changed after this comparison was saved. Run "
            "an explicit refresh before using it as current analysis."
        )
    if analysis.ruleset_version != COMPARISON_RULESET_VERSION:
        raise ComparisonSessionConflictError(
            "This comparison uses an older semantic ruleset. Refresh the "
            "explicit ordered pair before reopening it as current analysis."
        )


def open_comparison_session(
    analysis_uid: str,
    *,
    store: MemoryStore,
) -> ComparisonSessionSnapshot:
    """Open and revalidate one exact durable read-only analysis."""

    analysis = load_saved_comparison(analysis_uid, store=store)
    revalidate_saved_comparison(store, analysis)
    return ComparisonSessionSnapshot(
        analysis=analysis,
        version_token=comparison_canonical_digest(analysis.to_dict()),
    )


def prepare_comparison_refresh(
    analysis_uid: str,
    expected_version: str,
    *,
    store: MemoryStore,
) -> ComparisonSessionSnapshot:
    """Bind Refresh to the exact reviewed slot without requiring fresh sources."""

    expected = _version(expected_version)
    try:
        analysis = load_saved_comparison(analysis_uid, store=store)
    except ComparisonSessionUnavailableError as error:
        raise ComparisonSessionConflictError(
            "The saved comparison changed after this refresh was reviewed."
        ) from error
    current = comparison_canonical_digest(analysis.to_dict())
    if current != expected:
        raise ComparisonSessionConflictError(
            "The saved comparison changed after this refresh was reviewed."
        )
    return ComparisonSessionSnapshot(analysis=analysis, version_token=current)


__all__ = [
    "ComparisonSessionConflictError",
    "ComparisonSessionInputError",
    "ComparisonSessionSnapshot",
    "ComparisonSessionUnavailableError",
    "iter_saved_comparisons",
    "load_saved_comparison",
    "open_comparison_session",
    "prepare_comparison_refresh",
    "revalidate_saved_comparison",
]
