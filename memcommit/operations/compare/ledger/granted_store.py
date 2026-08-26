"""Durable Compare artifacts whose retention is authorized by grants."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable
import uuid

from memcommit.authority.access import (
    ContextAccess,
    GrantedReadStore,
    freeze_granted_context_binding,
    revalidate_granted_context_binding,
)
from memcommit.operations.compare.ledger.model import (
    ComparisonAnalysis,
    ComparisonError,
    comparison_canonical_digest,
)
from memcommit.context import Context, Memory
from memcommit.operations.compare.ledger.evidence import (
    ProjectedComparisonMemory,
    project_comparison_context,
)
from memcommit.context_targeting.loading import load_context_scope
from memcommit.derived_policy import AnalysisRetention, authorize_analysis_save
from memcommit.store import MemoryStore, _write_json_atomic
from memcommit.operations.update.model import GrantedUpdateTarget


_SCHEMA_VERSION = 1


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _uuid(value: str, label: str) -> str:
    try:
        canonical = str(uuid.UUID(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid {label}.") from error
    if canonical != value:
        raise ValueError(f"Invalid {label}.")
    return canonical


def granted_comparison_analyses_dir(store: MemoryStore) -> Path:
    return store.store_dir / "granted-comparison-analyses"


def granted_comparison_analysis_path(
    store: MemoryStore,
    reference_uid: str,
    compared_uid: str,
) -> Path:
    reference = _uuid(reference_uid, "comparison reference Context uid")
    compared = _uuid(compared_uid, "comparison compared Context uid")
    if reference == compared:
        raise ValueError("Comparison analysis requires distinct Context uids.")
    return granted_comparison_analyses_dir(store) / f"{reference}--{compared}.json"


@dataclass(frozen=True)
class GrantedComparisonArtifact:
    retention: AnalysisRetention
    analysis: ComparisonAnalysis
    bindings: tuple[GrantedUpdateTarget | None, GrantedUpdateTarget | None]

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "GRANTED_COMPARISON_ARTIFACT",
            "schema_version": _SCHEMA_VERSION,
            "retention": self.retention,
            "analysis": self.analysis.to_dict(),
            "bindings": [
                None if binding is None else binding.to_dict()
                for binding in self.bindings
            ],
        }

    @classmethod
    def from_dict(cls, value: object) -> "GrantedComparisonArtifact":
        if not isinstance(value, dict) or set(value) != {
            "kind",
            "schema_version",
            "retention",
            "analysis",
            "bindings",
        }:
            raise ValueError("Invalid granted comparison artifact.")
        if (
            value.get("kind") != "GRANTED_COMPARISON_ARTIFACT"
            or value.get("schema_version") != _SCHEMA_VERSION
            or value.get("retention") not in {"GRANT_BOUND", "RETAINED"}
        ):
            raise ValueError("Invalid granted comparison artifact.")
        raw_bindings = value.get("bindings")
        if not isinstance(raw_bindings, list) or len(raw_bindings) != 2:
            raise ValueError("Invalid granted comparison bindings.")
        bindings = tuple(
            None if item is None else GrantedUpdateTarget.from_dict(item)
            for item in raw_bindings
        )
        if all(binding is None for binding in bindings):
            raise ValueError("A granted comparison must bind a granted source.")
        try:
            analysis = ComparisonAnalysis.from_dict(value.get("analysis"))
        except ComparisonError as error:
            raise ValueError("Invalid granted comparison analysis.") from error
        for frame, binding in zip(analysis.frames, bindings, strict=True):
            if binding is not None and binding.public_name != frame.context_name:
                raise ValueError("Granted comparison binding does not match its frame.")
        return cls(
            retention=value["retention"],  # type: ignore[arg-type]
            analysis=analysis,
            bindings=bindings,  # type: ignore[arg-type]
        )


def load_granted_comparison_artifact(
    store: MemoryStore,
    reference_uid: str,
    compared_uid: str,
) -> GrantedComparisonArtifact | None:
    path = granted_comparison_analysis_path(store, reference_uid, compared_uid)
    if not path.exists():
        return None
    if not path.is_file() or path.is_symlink():
        raise ValueError("Granted comparison storage is invalid.")
    try:
        with open(path, encoding="utf-8") as file:
            value = json.load(file, object_pairs_hook=_strict_object)
        artifact = GrantedComparisonArtifact.from_dict(value)
    except (json.JSONDecodeError, ValueError) as error:
        raise ValueError("Saved granted comparison is invalid.") from error
    frames = artifact.analysis.frames
    if (
        frames[0].context_uid != reference_uid
        or frames[1].context_uid != compared_uid
    ):
        raise ValueError("Granted comparison does not match its storage key.")
    return artifact


def iter_granted_comparison_artifacts(
    store: MemoryStore,
) -> tuple[tuple[GrantedComparisonArtifact, Path], ...]:
    root = granted_comparison_analyses_dir(store)
    if not root.exists():
        return ()
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Granted comparison storage is invalid.")
    records: list[tuple[GrantedComparisonArtifact, Path]] = []
    for path in root.iterdir():
        if path.is_symlink() or not path.is_file() or not path.name.endswith(".json"):
            raise ValueError("Granted comparison storage is invalid.")
        parts = path.stem.split("--")
        if len(parts) != 2:
            raise ValueError("Granted comparison storage is invalid.")
        artifact = load_granted_comparison_artifact(store, parts[0], parts[1])
        assert artifact is not None
        records.append((artifact, path))
    return tuple(sorted(records, key=lambda record: record[0].analysis.uid))


def save_granted_comparison_artifact(
    store: MemoryStore,
    analysis: ComparisonAnalysis,
    accesses: Iterable[ContextAccess],
    *,
    retention: AnalysisRetention,
    expected_analysis_uid: str | None,
    expected_analysis_version: str | None = None,
) -> GrantedComparisonArtifact:
    values = tuple(accesses)
    if len(values) != 2:
        raise ValueError("Compare persistence requires two source accesses.")
    authorize_analysis_save(values, retention=retention)
    bindings = tuple(
        freeze_granted_context_binding(access) if access.is_granted else None
        for access in values
    )
    artifact = GrantedComparisonArtifact(
        retention=retention,
        analysis=analysis,
        bindings=bindings,  # type: ignore[arg-type]
    )
    restored = GrantedComparisonArtifact.from_dict(artifact.to_dict())
    if expected_analysis_version is not None and (
        not isinstance(expected_analysis_version, str)
        or len(expected_analysis_version) != 64
        or any(
            character not in "0123456789abcdef"
            for character in expected_analysis_version
        )
    ):
        raise ValueError("Invalid expected comparison analysis version.")
    path = granted_comparison_analysis_path(
        store,
        analysis.frames[0].context_uid,
        analysis.frames[1].context_uid,
    )
    with store._command_write_lock():
        with store.profile_write_guard():
            root = path.parent
            if root.exists() and (not root.is_dir() or root.is_symlink()):
                raise ValueError("Granted comparison storage is invalid.")
            root.mkdir(parents=True, exist_ok=True)
            if path.exists() and (not path.is_file() or path.is_symlink()):
                raise ValueError("Granted comparison storage is invalid.")
            current = load_granted_comparison_artifact(
                store,
                analysis.frames[0].context_uid,
                analysis.frames[1].context_uid,
            )
            current_uid = (
                current.analysis.uid if current is not None else None
            )
            current_version = (
                comparison_canonical_digest(current.analysis.to_dict())
                if current is not None
                else None
            )
            if current_uid != expected_analysis_uid or (
                expected_analysis_version is not None
                and current_version != expected_analysis_version
            ):
                raise ValueError(
                    "The granted comparison slot changed before this analysis "
                    "could be saved."
                )
            _write_json_atomic(path, restored.to_dict())
    return restored


def granted_artifact_contexts(
    store: MemoryStore,
    artifact: GrantedComparisonArtifact,
) -> tuple[Context, Context]:
    """Open live bound sources or reconstruct explicitly retained snapshots."""

    if artifact.retention == "RETAINED":
        contexts: list[Context] = []
        for frame in artifact.analysis.frames:
            context = Context(uid=frame.context_uid, name=frame.context_name)
            # Focused Compare frames keep non-actionable neighbors as Context
            # evidence, but that evidence remains part of the frozen Context
            # digest and must be restored for exact session revalidation.
            for memory in sorted(
                (*frame.memories, *frame.context_evidence),
                key=lambda item: item.position,
            ):
                context.add(
                    ProjectedComparisonMemory(
                        uid=memory.uid,
                        content=memory.content,
                        source=memory.source,
                    )
                    if memory.source is not None
                    else Memory(uid=memory.uid, content=memory.content)
                )
            contexts.append(context)
        return contexts[0], contexts[1]

    contexts = []
    for frame, binding, include_descendants in zip(
        artifact.analysis.frames,
        artifact.bindings,
        artifact.analysis.include_descendants,
        strict=True,
    ):
        if binding is None:
            context = recursive_comparison_projection(
                load_context_scope(
                    store,
                    frame.context_name,
                    include_descendants=include_descendants,
                )
            )
        else:
            access = revalidate_granted_context_binding(binding)
            context = recursive_comparison_projection(
                load_context_scope(
                    GrantedReadStore(access),
                    binding.public_name,
                    include_descendants=include_descendants,
                )
            )
        contexts.append(context)
    if not artifact.analysis.matches(contexts[0], contexts[1]):
        raise ValueError(
            "A grant-bound comparison source changed after the analysis was saved."
        )
    return contexts[0], contexts[1]


def recursive_comparison_projection(root: Context) -> Context:
    return project_comparison_context(root)
