"""Exact Study prewarms for the standalone Context understanding summary.

Summarize has no durable ordinary session.  Its immutable artifact therefore
remains in the Study bundle and materializes only the typed result of the
explicit invocation.  No parent/child projection or cross-frame composition is
accepted: direct and recursive requests have distinct exact keys.
"""

from __future__ import annotations

from memcommit.infrastructure.config import Config
from memcommit.infrastructure.providers.policy import (
    resolve_operation_provider_policy,
)
from memcommit.persistence.store import MemoryStore
from memcommit.application.operations.summarize.model import (
    SUMMARIZE_PROVIDER_CONTRACT_VERSION,
    SUMMARIZE_TEXT_LIMIT,
    SummaryFrame,
)
from memcommit.semantic.understanding import (
    UnderstandingError,
    UnderstandingSummary,
    normalize_understanding_text,
)
from memcommit.study_prewarm.installations import declared_artifact_available
from memcommit.study_prewarm.quality import (
    SemanticIdentity,
    compatible_cached_identities,
    highest_quality_candidates,
)
from memcommit.study_prewarm.registry import (
    StudyPrewarmRegistryError,
    load_artifact,
    load_registry,
    payload_digest,
)


SUMMARIZE_ARTIFACT_KIND = "STUDY_SUMMARIZE_EXACT_PREWARM"
SUMMARIZE_ARTIFACT_SCHEMA_VERSION = 1


def _task_root(name: str) -> str | None:
    root = name.split("/", 1)[0]
    if root == "practice":
        return "tutorial"
    if root in {"task-1", "task-2", "task-3"}:
        return root
    return None


def _configured_semantic_identity() -> tuple[str, str | None, str | None]:
    resolved = resolve_operation_provider_policy(
        "summarize_context",
        config=Config(),
        mode="STUDY_PARTICIPANT",
    )
    return resolved.provider_id, resolved.model, resolved.reasoning_effort


def _frame_identity(frame: SummaryFrame) -> dict[str, object]:
    return {
        "context_uid": frame.context_uid,
        "context_name": frame.context_name,
        "include_descendants": frame.include_descendants,
        "follow_embeds": frame.follow_embeds,
        "digest": frame.digest,
        "sources": [
            {
                "context_uid": source.context_uid,
                "context_name": source.context_name,
                "memory_uid": source.memory_uid,
            }
            for source in frame.sources
        ],
    }


def _key_material(
    *,
    task: str,
    frame_identity: dict[str, object],
    provider: str,
    model: str,
    reasoning: str | None,
) -> dict[str, object]:
    return {
        "operation": "SUMMARIZE",
        "task": task,
        "provider": provider,
        "model": model,
        "reasoning": reasoning,
        "provider_contract_version": SUMMARIZE_PROVIDER_CONTRACT_VERSION,
        "frame": frame_identity,
    }


def summarize_prewarm_key(
    *,
    task: str,
    frame: SummaryFrame,
    provider: str,
    model: str,
    reasoning: str | None,
) -> str:
    """Return the registry key computable before opening artifact bytes."""

    return payload_digest(
        _key_material(
            task=task,
            frame_identity=_frame_identity(frame),
            provider=provider,
            model=model,
            reasoning=reasoning,
        )
    )


def build_summarize_prewarm_artifact(
    *,
    task: str,
    frame: SummaryFrame,
    understanding: UnderstandingSummary,
    provider: str,
    model: str,
    reasoning: str | None,
    offline_provider_seconds: float,
) -> tuple[str, dict[str, object]]:
    """Build one portable result for an actually executed whole frame."""

    source_uids = {source.memory_uid for source in frame.sources}
    if (
        task not in {"tutorial", "task-1", "task-2", "task-3"}
        or _task_root(frame.context_name) != task
        or not frame.sources
        or not isinstance(provider, str)
        or not provider
        or not isinstance(model, str)
        or not model
        or (reasoning is not None and not isinstance(reasoning, str))
        or not isinstance(offline_provider_seconds, (int, float))
        or isinstance(offline_provider_seconds, bool)
        or offline_provider_seconds < 0
        or any(uid not in source_uids for uid in understanding.source_uids)
    ):
        raise StudyPrewarmRegistryError("Summarize prewarm basis is invalid.")
    frame_identity = _frame_identity(frame)
    material = _key_material(
        task=task,
        frame_identity=frame_identity,
        provider=provider,
        model=model,
        reasoning=reasoning,
    )
    key = payload_digest(material)
    understanding_value = understanding.to_dict()
    return key, {
        "kind": SUMMARIZE_ARTIFACT_KIND,
        "schema_version": SUMMARIZE_ARTIFACT_SCHEMA_VERSION,
        "key": key,
        **material,
        "offline_provider_seconds": float(offline_provider_seconds),
        "understanding_digest": payload_digest(understanding_value),
        "understanding": understanding_value,
    }


def _validate_frame_identity(value: object) -> dict[str, object]:
    expected = {
        "context_uid",
        "context_name",
        "include_descendants",
        "follow_embeds",
        "digest",
        "sources",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise StudyPrewarmRegistryError("Summarize prewarm frame is invalid.")
    sources = value.get("sources")
    if (
        not isinstance(value.get("context_uid"), str)
        or not value.get("context_uid")
        or not isinstance(value.get("context_name"), str)
        or not value.get("context_name")
        or type(value.get("include_descendants")) is not bool
        or type(value.get("follow_embeds")) is not bool
        or not isinstance(value.get("digest"), str)
        or len(str(value.get("digest"))) != 64
        or not isinstance(sources, list)
        or not sources
    ):
        raise StudyPrewarmRegistryError("Summarize prewarm frame is invalid.")
    expected_source_fields = {"context_uid", "context_name", "memory_uid"}
    if any(
        not isinstance(source, dict)
        or set(source) != expected_source_fields
        or any(not isinstance(source.get(field), str) or not source.get(field) for field in expected_source_fields)
        for source in sources
    ):
        raise StudyPrewarmRegistryError("Summarize prewarm sources are invalid.")
    return value


def _validate_artifact(
    value: dict[str, object],
    *,
    entry_key: str,
    entry_task: str,
) -> UnderstandingSummary:
    if (
        value.get("kind") != SUMMARIZE_ARTIFACT_KIND
        or value.get("schema_version") != SUMMARIZE_ARTIFACT_SCHEMA_VERSION
        or value.get("key") != entry_key
        or value.get("operation") != "SUMMARIZE"
        or value.get("task") != entry_task
        or value.get("provider_contract_version")
        != SUMMARIZE_PROVIDER_CONTRACT_VERSION
        or not isinstance(value.get("provider"), str)
        or not isinstance(value.get("model"), str)
        or (
            value.get("reasoning") is not None
            and not isinstance(value.get("reasoning"), str)
        )
    ):
        raise StudyPrewarmRegistryError("Declared Summarize prewarm is invalid.")
    frame_identity = _validate_frame_identity(value.get("frame"))
    material = _key_material(
        task=entry_task,
        frame_identity=frame_identity,
        provider=str(value["provider"]),
        model=str(value["model"]),
        reasoning=value.get("reasoning"),  # type: ignore[arg-type]
    )
    if payload_digest(material) != entry_key:
        raise StudyPrewarmRegistryError("Declared Summarize key is stale.")
    raw_understanding = value.get("understanding")
    if (
        not isinstance(raw_understanding, dict)
        or set(raw_understanding) != {"text", "source_uids"}
        or not isinstance(raw_understanding.get("source_uids"), list)
        or value.get("understanding_digest") != payload_digest(raw_understanding)
    ):
        raise StudyPrewarmRegistryError("Summarize understanding is invalid.")
    try:
        understanding = UnderstandingSummary(
            text=normalize_understanding_text(
                raw_understanding.get("text"),
                limit=SUMMARIZE_TEXT_LIMIT,
            ),
            source_uids=tuple(raw_understanding["source_uids"]),
        )
    except (UnderstandingError, TypeError) as error:
        raise StudyPrewarmRegistryError(
            "Summarize understanding is invalid."
        ) from error
    source_uids = {
        str(source["memory_uid"])
        for source in frame_identity["sources"]  # type: ignore[union-attr]
    }
    if any(uid not in source_uids for uid in understanding.source_uids):
        raise StudyPrewarmRegistryError(
            "Summarize understanding cites unknown evidence."
        )
    return understanding


def find_declared_summarize_prewarm(
    *,
    store: MemoryStore,
    frame: SummaryFrame,
) -> UnderstandingSummary | None:
    """Load only the exact artifact requested by one explicit invocation."""

    registry = load_registry(store.store_dir)
    task = _task_root(frame.context_name)
    if registry is None or task is None or not frame.sources:
        return None
    requested_identity = _configured_semantic_identity()
    if requested_identity[1] is None:
        return None
    candidate_keys: dict[str, SemanticIdentity] = {}
    for cached_identity in compatible_cached_identities(requested_identity):
        provider, model, reasoning = cached_identity
        assert model is not None
        candidate_keys[
            summarize_prewarm_key(
                task=task,
                frame=frame,
                provider=provider,
                model=model,
                reasoning=reasoning,
            )
        ] = cached_identity
    candidates: list[tuple[SemanticIdentity, UnderstandingSummary]] = []
    for entry in registry.entries:
        if (
            not entry.enabled
            or entry.operation != "SUMMARIZE"
            or entry.task != task
            or entry.key not in candidate_keys
        ):
            continue
        artifact = load_artifact(store.store_dir, entry)
        understanding = _validate_artifact(
            artifact,
            entry_key=entry.key,
            entry_task=entry.task,
        )
        if not declared_artifact_available(
            store,
            entry=entry,
            evidence={
                "frame_digest": frame.digest,
                "understanding_digest": str(artifact["understanding_digest"]),
            },
        ):
            continue
        candidates.append((candidate_keys[entry.key], understanding))
    selected = highest_quality_candidates(candidates)
    if len(selected) > 1:
        raise StudyPrewarmRegistryError(
            "Multiple declared Summarize prewarms match the exact frame."
        )
    return selected[0] if selected else None
