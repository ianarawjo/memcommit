"""Setup-time installation of the exact Tutorial Atomize analysis."""

from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from memcommit.application.operations.atomize.domain import (
    ATOMIZE_PROVIDER_CONTRACT_VERSION,
    ATOMIZE_RULESET_VERSION,
    AtomizeAnalysisSession,
    atomize_analysis_matches_context,
)
from memcommit.infrastructure.config import Config
from memcommit.infrastructure.providers.policy import (
    resolve_operation_provider_policy,
)
from memcommit.context import Context, Memory
from memcommit.application.operations.profile.config import ProfileEntry, ProfileRegistry, study_run_identity
from memcommit.application.operations.profile.model import (
    _LEGACY_PRE_SPLIT_STUDY_PRACTICE_DESCRIPTION_CONTENT,
    _LEGACY_STUDY_PRACTICE_DESCRIPTION_OVERVIEW_CONTENT,
    _LEGACY_STUDY_PRACTICE_DESCRIPTION_SITUATION_CONTENT,
    _PRE_SPLIT_STUDY_PRACTICE_DESCRIPTION_CONTENT,
    _STUDY_PRACTICE_DESCRIPTION_OVERVIEW_CONTENT,
    _STUDY_PRACTICE_DESCRIPTION_SITUATION_CONTENT,
    _STUDY_PRACTICE_DESCRIPTION_SITUATION_UID,
    _STUDY_PRACTICE_DESCRIPTION_TASK_CONTENT,
    _STUDY_PRACTICE_DESCRIPTION_TASK_UID,
)
from memcommit.application.operations.review.model import direct_context_digest
from memcommit.semantic.prompt_policy import (
    GENERAL_PROMPT_POLICY_ID,
    STUDY_PROMPT_POLICY_ID,
)
from memcommit.persistence.store import MemoryStore, context_record_digest
from memcommit.study_prewarm.installations import (
    INSTALLATIONS_DIRECTORY_NAME,
    declared_artifact_available,
    declared_installation_matches,
    record_declared_installation,
)
from memcommit.study_prewarm.quality import (
    SemanticIdentity,
    highest_quality_candidates,
    prewarm_quality_satisfies,
)
from memcommit.study_prewarm.registry import (
    StudyPrewarmRegistryError,
    load_artifact,
    load_registry,
    payload_digest,
)


ATOMIZE_ARTIFACT_KIND = "STUDY_ATOMIZE_EXACT_PREWARM"
ATOMIZE_ARTIFACT_SCHEMA_VERSION = 2
_LEGACY_PRACTICE_PROVENANCE_UID = "5faaf0a4-d5b8-54d0-af25-c056e9058c98"
_LEGACY_PRACTICE_PROVENANCE_CONTENT = (
    "The practice source is a synthetic editing request supplied for this "
    "study. It has no external bibliographic source."
)


@dataclass(frozen=True)
class AtomizePrewarmInstallResult:
    declared: int
    installed: int
    skipped_configuration: int
    analysis_uids: tuple[str, ...]


@dataclass(frozen=True)
class AtomizePrewarmMatch:
    """One installed hidden artifact ready for first-use materialization."""

    entry_key: str
    analysis: AtomizeAnalysisSession
    output_context_name: str


def _content_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _analysis_digest(analysis: AtomizeAnalysisSession) -> str:
    return payload_digest(analysis.to_dict())


def _analysis_source_digest(analysis: AtomizeAnalysisSession) -> str:
    encoded = json.dumps(
        [
            {"uid": item.memory_uid, "content": item.content}
            for item in analysis.items
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _analysis_has_complete_source_ledger(
    analysis: AtomizeAnalysisSession,
) -> bool:
    return (
        analysis.memory_count == len(analysis.items)
        and [item.position for item in analysis.items]
        == list(range(len(analysis.items)))
        and analysis.context_digest == _analysis_source_digest(analysis)
    )


def _description_matches_prepared_digest(
    description: Context,
    prepared_digest: str,
) -> bool:
    if context_record_digest(description) == prepared_digest:
        return True
    if (
        description.name != "practice/description"
        or _LEGACY_PRACTICE_PROVENANCE_UID in description.memories
    ):
        return False
    # Older retained artifacts may bind the pre-split description, the retired
    # brand name, one retired provenance-only Memory, or a combination of
    # those exact states. Reconstruct them only in memory; none may be saved
    # into the participant Context.
    variants = [copy.deepcopy(description)]
    legacy_brand = copy.deepcopy(description)
    brand_replacements = {
        _STUDY_PRACTICE_DESCRIPTION_OVERVIEW_CONTENT: (
            _LEGACY_STUDY_PRACTICE_DESCRIPTION_OVERVIEW_CONTENT
        ),
        _STUDY_PRACTICE_DESCRIPTION_SITUATION_CONTENT: (
            _LEGACY_STUDY_PRACTICE_DESCRIPTION_SITUATION_CONTENT
        ),
    }
    for item in legacy_brand.iter_items():
        if isinstance(item, Memory) and item.content in brand_replacements:
            item.content = brand_replacements[item.content]
    if context_record_digest(legacy_brand) != context_record_digest(description):
        variants.append(legacy_brand)
    for variant in tuple(variants):
        situation = variant.memories.get(
            _STUDY_PRACTICE_DESCRIPTION_SITUATION_UID
        )
        task = variant.memories.get(_STUDY_PRACTICE_DESCRIPTION_TASK_UID)
        if (
            isinstance(situation, Memory)
            and isinstance(task, Memory)
            and task.content == _STUDY_PRACTICE_DESCRIPTION_TASK_CONTENT
            and situation.content
            in {
                _STUDY_PRACTICE_DESCRIPTION_SITUATION_CONTENT,
                _LEGACY_STUDY_PRACTICE_DESCRIPTION_SITUATION_CONTENT,
            }
        ):
            pre_split = copy.deepcopy(variant)
            pre_split.remove(_STUDY_PRACTICE_DESCRIPTION_SITUATION_UID)
            pre_split_task = pre_split.memories[
                _STUDY_PRACTICE_DESCRIPTION_TASK_UID
            ]
            assert isinstance(pre_split_task, Memory)
            pre_split_task.content = (
                _LEGACY_PRE_SPLIT_STUDY_PRACTICE_DESCRIPTION_CONTENT
                if situation.content
                == _LEGACY_STUDY_PRACTICE_DESCRIPTION_SITUATION_CONTENT
                else _PRE_SPLIT_STUDY_PRACTICE_DESCRIPTION_CONTENT
            )
            variants.append(pre_split)
    for variant in tuple(variants):
        with_provenance = copy.deepcopy(variant)
        with_provenance.add(
            Memory(
                uid=_LEGACY_PRACTICE_PROVENANCE_UID,
                content=_LEGACY_PRACTICE_PROVENANCE_CONTENT,
            )
        )
        variants.append(with_provenance)
    return any(
        context_record_digest(variant) == prepared_digest for variant in variants
    )


def _key_material(
    *,
    task_description: dict[str, str],
    analysis: AtomizeAnalysisSession,
    provider: object,
    model: object,
    reasoning: object,
) -> dict[str, object]:
    return {
        "operation": "ATOMIZE",
        "task": "tutorial",
        "provider": provider,
        "model": model,
        "reasoning": reasoning,
        "provider_contract_version": ATOMIZE_PROVIDER_CONTRACT_VERSION,
        "ruleset_version": ATOMIZE_RULESET_VERSION,
        "prompt_policy_id": analysis.prompt_policy_id,
        "task_description": task_description,
        "source": {
            "context_uid": analysis.context_uid,
            "context_name": analysis.context_name,
            "context_digest": analysis.context_digest,
            "memories": [
                {
                    "uid": item.memory_uid,
                    "position": item.position,
                    "content_digest": _content_digest(item.content),
                }
                for item in analysis.items
            ],
        },
    }


def _legacy_key_material(
    *,
    task_description: dict[str, str],
    analysis: AtomizeAnalysisSession,
    provider: object,
    model: object,
    reasoning: object,
) -> dict[str, object]:
    """Reconstruct schema-v1 keys so old full-example artifacts can be skipped."""

    material = _key_material(
        task_description=task_description,
        analysis=analysis,
        provider=provider,
        model=model,
        reasoning=reasoning,
    )
    material.pop("prompt_policy_id")
    return material


def build_atomize_prewarm_artifact(
    *,
    task_description: Context,
    analysis: AtomizeAnalysisSession,
    provider: str,
    model: str,
    reasoning: str | None,
    offline_provider_seconds: float,
) -> tuple[str, dict[str, object]]:
    """Build one portable exact Tutorial Atomize semantic payload."""

    if (
        analysis.context_name != "practice/source"
        or analysis.ruleset_version != ATOMIZE_RULESET_VERSION
        or analysis.prompt_policy_id != STUDY_PROMPT_POLICY_ID
        or analysis.declared_frames
        or analysis.source_review_uid is not None
        or analysis.source_review_digest is not None
        or not _analysis_has_complete_source_ledger(analysis)
    ):
        raise StudyPrewarmRegistryError(
            "Tutorial Atomize prewarm must be the unmodified practice Source."
        )
    if task_description.name != "practice/description":
        raise StudyPrewarmRegistryError("Tutorial Atomize description is invalid.")
    if (
        not isinstance(provider, str)
        or not provider
        or not isinstance(model, str)
        or not model
        or (reasoning is not None and not isinstance(reasoning, str))
        or not isinstance(offline_provider_seconds, (int, float))
        or isinstance(offline_provider_seconds, bool)
        or offline_provider_seconds < 0
    ):
        raise StudyPrewarmRegistryError("Atomize provider evidence is invalid.")
    description = {
        "name": task_description.name,
        "context_uid": task_description.uid,
        "context_digest": context_record_digest(task_description),
    }
    key = payload_digest(
        _key_material(
            task_description=description,
            analysis=analysis,
            provider=provider,
            model=model,
            reasoning=reasoning,
        )
    )
    return key, {
        "kind": ATOMIZE_ARTIFACT_KIND,
        "schema_version": ATOMIZE_ARTIFACT_SCHEMA_VERSION,
        "key": key,
        "task": "tutorial",
        "operation": "ATOMIZE",
        "provider": provider,
        "model": model,
        "reasoning": reasoning,
        "provider_contract_version": ATOMIZE_PROVIDER_CONTRACT_VERSION,
        "ruleset_version": ATOMIZE_RULESET_VERSION,
        "prompt_policy_id": analysis.prompt_policy_id,
        "task_description": description,
        "offline_provider_seconds": float(offline_provider_seconds),
        "analysis_digest": _analysis_digest(analysis),
        "analysis": analysis.to_dict(),
    }


def _configured_semantic_identity() -> tuple[str, str | None, str | None]:
    resolved = resolve_operation_provider_policy(
        "impact_atomize",
        config=Config(),
        mode="STUDY_PARTICIPANT",
    )
    return resolved.provider_id, resolved.model, resolved.reasoning_effort


def _validate_artifact(
    value: dict[str, object],
    *,
    entry_key: str,
) -> tuple[AtomizeAnalysisSession, dict[str, str]]:
    common_expected = {
        "kind",
        "schema_version",
        "key",
        "task",
        "operation",
        "provider",
        "model",
        "reasoning",
        "provider_contract_version",
        "ruleset_version",
        "task_description",
        "offline_provider_seconds",
        "analysis_digest",
        "analysis",
    }
    schema_version = value.get("schema_version")
    legacy = schema_version == 1
    expected = (
        common_expected
        if legacy
        else common_expected | {"prompt_policy_id"}
    )
    prompt_policy_id = (
        GENERAL_PROMPT_POLICY_ID
        if legacy
        else value.get("prompt_policy_id")
    )
    if set(value) != expected or (
        value.get("kind") != ATOMIZE_ARTIFACT_KIND
        or schema_version not in {1, ATOMIZE_ARTIFACT_SCHEMA_VERSION}
        or value.get("key") != entry_key
        or value.get("task") != "tutorial"
        or value.get("operation") != "ATOMIZE"
        or value.get("provider_contract_version")
        != ATOMIZE_PROVIDER_CONTRACT_VERSION
        or value.get("ruleset_version") != ATOMIZE_RULESET_VERSION
        or prompt_policy_id
        not in {GENERAL_PROMPT_POLICY_ID, STUDY_PROMPT_POLICY_ID}
    ):
        raise StudyPrewarmRegistryError("Declared Atomize prewarm is invalid.")
    provider = value.get("provider")
    model = value.get("model")
    reasoning = value.get("reasoning")
    offline_seconds = value.get("offline_provider_seconds")
    if (
        not isinstance(provider, str)
        or not provider
        or not isinstance(model, str)
        or not model
        or (reasoning is not None and not isinstance(reasoning, str))
        or not isinstance(offline_seconds, (int, float))
        or isinstance(offline_seconds, bool)
        or offline_seconds < 0
    ):
        raise StudyPrewarmRegistryError("Atomize provider evidence is invalid.")
    try:
        analysis = AtomizeAnalysisSession.from_dict(value.get("analysis"))
    except Exception as error:
        raise StudyPrewarmRegistryError(
            "Declared Atomize analysis is invalid."
        ) from error
    description = value.get("task_description")
    if (
        not isinstance(description, dict)
        or set(description) != {"name", "context_uid", "context_digest"}
        or not all(isinstance(description.get(key), str) for key in description)
    ):
        raise StudyPrewarmRegistryError("Atomize task description binding is invalid.")
    if (
        analysis.context_name != "practice/source"
        or analysis.ruleset_version != ATOMIZE_RULESET_VERSION
        or analysis.prompt_policy_id != prompt_policy_id
        or analysis.declared_frames
        or not _analysis_has_complete_source_ledger(analysis)
        or value.get("analysis_digest")
        != (
            payload_digest(value.get("analysis"))
            if legacy
            else _analysis_digest(analysis)
        )
    ):
        raise StudyPrewarmRegistryError("Declared Atomize analysis digest is stale.")
    expected_key = payload_digest(
        (_legacy_key_material if legacy else _key_material)(
            task_description=description,  # type: ignore[arg-type]
            analysis=analysis,
            provider=provider,
            model=model,
            reasoning=reasoning,
        )
    )
    if expected_key != entry_key:
        raise StudyPrewarmRegistryError("Atomize prewarm key is stale.")
    return analysis, description  # type: ignore[return-value]


def _installation_path(store: MemoryStore, analysis_uid: str) -> Path:
    return (
        store.store_dir
        / INSTALLATIONS_DIRECTORY_NAME
        / f"atomize-{analysis_uid}.json"
    )


def _installation_evidence(
    *,
    analysis: AtomizeAnalysisSession,
    description: dict[str, str],
) -> dict[str, str]:
    return {
        "analysis_digest": _analysis_digest(analysis),
        "source_context_uid": analysis.context_uid,
        "source_context_digest": analysis.context_digest,
        "description_context_uid": description["context_uid"],
        "description_context_digest": description["context_digest"],
    }


def is_installed_atomize_prewarm(
    store: MemoryStore,
    analysis: AtomizeAnalysisSession,
) -> bool:
    """Recognize a legacy materialized receipt or the installed artifact."""

    path = _installation_path(store, analysis.uid)
    if path.exists():
        if not path.is_file() or path.is_symlink():
            raise StudyPrewarmRegistryError("Atomize prewarm receipt is unsafe.")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise StudyPrewarmRegistryError(
                "Atomize prewarm receipt is invalid."
            ) from error
        if (
            isinstance(value, dict)
            and value.get("kind") == "STUDY_ATOMIZE_PREWARM_INSTALLATION"
            and value.get("schema_version") == 1
            and value.get("analysis_uid") == analysis.uid
            and value.get("analysis_digest") == _analysis_digest(analysis)
        ):
            return True

    registry = load_registry(store.store_dir)
    if registry is None:
        return False
    for entry in registry.entries:
        if not entry.enabled or entry.operation != "ATOMIZE":
            continue
        artifact = load_artifact(store.store_dir, entry)
        prepared, description = _validate_artifact(artifact, entry_key=entry.key)
        if prepared != analysis:
            continue
        if declared_installation_matches(
            store,
            entry=entry,
            evidence=_installation_evidence(
                analysis=prepared,
                description=description,
            ),
        ):
            return True
    return False


def find_declared_atomize_prewarm(
    *,
    store: MemoryStore,
    context: Context,
) -> AtomizePrewarmMatch | None:
    """Resolve one hidden exact artifact without publishing ordinary state."""

    registry = load_registry(store.store_dir)
    if registry is None:
        return None
    requested_identity = _configured_semantic_identity()
    matches: list[tuple[bool, SemanticIdentity, AtomizePrewarmMatch]] = []
    for entry in registry.entries:
        if not entry.enabled or entry.operation != "ATOMIZE":
            continue
        artifact = load_artifact(store.store_dir, entry)
        analysis, description = _validate_artifact(artifact, entry_key=entry.key)
        if analysis.prompt_policy_id != STUDY_PROMPT_POLICY_ID:
            continue
        cached_identity = (
            artifact.get("provider"),
            artifact.get("model"),
            artifact.get("reasoning"),
        )
        if not prewarm_quality_satisfies(
            cached_identity,  # type: ignore[arg-type]
            requested_identity,
        ):
            continue
        if not declared_artifact_available(
            store,
            entry=entry,
            evidence=_installation_evidence(
                analysis=analysis,
                description=description,
            ),
        ):
            continue
        current_description = store.load_direct(description["name"])
        exact_description = (
            context_record_digest(current_description)
            == description["context_digest"]
        )
        if (
            current_description.uid != description["context_uid"]
            or not _description_matches_prepared_digest(
                current_description,
                description["context_digest"],
            )
        ):
            continue
        if (
            context.uid != analysis.context_uid
            or context.name != analysis.context_name
            or direct_context_digest(context) != analysis.context_digest
            or not atomize_analysis_matches_context(analysis, context)
        ):
            continue
        matches.append(
            (
                exact_description,
                cached_identity,  # type: ignore[arg-type]
                AtomizePrewarmMatch(
                    entry_key=entry.key,
                    analysis=analysis,
                    output_context_name="practice/source-atomized",
                ),
            )
        )
    exact_matches = [match for match in matches if match[0]]
    eligible_matches = exact_matches or matches
    selected = highest_quality_candidates(
        [(identity, match) for _exact, identity, match in eligible_matches]
    )
    if len(selected) > 1:
        raise StudyPrewarmRegistryError(
            "Multiple declared Atomize prewarms match the current Source."
        )
    return selected[0] if selected else None


def install_declared_atomize_prewarms(
    *,
    store: MemoryStore,
    profile: ProfileEntry,
    registry_snapshot: ProfileRegistry,
    publish: bool = True,
) -> AtomizePrewarmInstallResult:
    """Validate the tutorial seed and install only its hidden receipt."""

    registry = load_registry(store.store_dir)
    if registry is None:
        return AtomizePrewarmInstallResult(0, 0, 0, ())
    identity = study_run_identity(profile)
    if identity is None or identity.role != "PARTICIPANT":
        raise StudyPrewarmRegistryError(
            "Declared Study prewarms require a participant Study Profile."
        )
    if registry.baseline_profile_uid != identity.baseline_profile_uid:
        raise StudyPrewarmRegistryError(
            "Study prewarm registry belongs to a different baseline."
        )
    requested_identity = _configured_semantic_identity()
    installed = 0
    declared = 0
    skipped = 0
    for entry in registry.entries:
        if not entry.enabled or entry.operation != "ATOMIZE":
            continue
        declared += 1
        if entry.task != "tutorial":
            raise StudyPrewarmRegistryError("Atomize prewarm belongs to an invalid task.")
        artifact = load_artifact(store.store_dir, entry)
        analysis, description = _validate_artifact(
            artifact,
            entry_key=entry.key,
        )
        if analysis.prompt_policy_id != STUDY_PROMPT_POLICY_ID:
            # Schema-v1 artifacts were produced with the old full-example
            # prompt. Keep them readable for migration diagnostics, but never
            # install them as a rules-only Study provider substitute.
            skipped += 1
            continue
        cached_identity = (
            artifact.get("provider"),
            artifact.get("model"),
            artifact.get("reasoning"),
        )
        if not prewarm_quality_satisfies(
            cached_identity,  # type: ignore[arg-type]
            requested_identity,
        ):
            skipped += 1
            continue
        source = store.load_direct(analysis.context_name)
        current_description = store.load_direct(description["name"])
        if (
            current_description.uid != description["context_uid"]
            or not _description_matches_prepared_digest(
                current_description,
                description["context_digest"],
            )
        ):
            raise StudyPrewarmRegistryError(
                "Tutorial instruction changed after Atomize was prepared."
            )
        if (
            direct_context_digest(source) != analysis.context_digest
            or not atomize_analysis_matches_context(analysis, source)
        ):
            raise StudyPrewarmRegistryError(
                "Declared Atomize prewarm does not match the current Source."
            )
        if publish:
            record_declared_installation(
                store,
                entry=entry,
                evidence=_installation_evidence(
                    analysis=analysis,
                    description=description,
                ),
            )
            installed += 1
    return AtomizePrewarmInstallResult(
        declared=declared,
        installed=installed,
        skipped_configuration=skipped,
        # A hidden receipt intentionally has no ordinary session identity.
        analysis_uids=(),
    )
