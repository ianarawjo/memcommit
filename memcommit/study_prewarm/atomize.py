"""Setup-time installation of the exact Tutorial Atomize analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from memcommit.atomize import (
    ATOMIZE_PROVIDER_CONTRACT_VERSION,
    ATOMIZE_RULESET_VERSION,
    AtomizeAnalysisSession,
    atomize_analysis_matches_context,
)
from memcommit.atomize_workflow import install_prepared_atomize_analysis
from memcommit.config import Config
from memcommit.context import Context
from memcommit.profile_config import ProfileEntry, ProfileRegistry, study_run_identity
from memcommit.review import direct_context_digest
from memcommit.store import MemoryStore, _write_json_atomic, context_record_digest
from memcommit.study_prewarm.compare import INSTALLATIONS_DIRECTORY_NAME
from memcommit.study_prewarm.registry import (
    StudyPrewarmRegistryError,
    load_artifact,
    load_registry,
    payload_digest,
)


ATOMIZE_ARTIFACT_KIND = "STUDY_ATOMIZE_EXACT_PREWARM"
ATOMIZE_ARTIFACT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class AtomizePrewarmInstallResult:
    declared: int
    installed: int
    skipped_configuration: int
    analysis_uids: tuple[str, ...]


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
        "task_description": description,
        "offline_provider_seconds": float(offline_provider_seconds),
        "analysis_digest": _analysis_digest(analysis),
        "analysis": analysis.to_dict(),
    }


def _configured_semantic_identity() -> tuple[str, str | None, str | None]:
    config = Config()
    provider = config.semantic_provider()
    model = config.model_for_provider(provider)
    reasoning = (
        config.codex_reasoning_effort()
        if provider == "codex_chatgpt"
        else None
    )
    return provider, model, reasoning


def _validate_artifact(
    value: dict[str, object],
    *,
    entry_key: str,
) -> tuple[AtomizeAnalysisSession, dict[str, str]]:
    expected = {
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
    if set(value) != expected or (
        value.get("kind") != ATOMIZE_ARTIFACT_KIND
        or value.get("schema_version") != ATOMIZE_ARTIFACT_SCHEMA_VERSION
        or value.get("key") != entry_key
        or value.get("task") != "tutorial"
        or value.get("operation") != "ATOMIZE"
        or value.get("provider_contract_version")
        != ATOMIZE_PROVIDER_CONTRACT_VERSION
        or value.get("ruleset_version") != ATOMIZE_RULESET_VERSION
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
        or analysis.declared_frames
        or not _analysis_has_complete_source_ledger(analysis)
        or value.get("analysis_digest") != _analysis_digest(analysis)
    ):
        raise StudyPrewarmRegistryError("Declared Atomize analysis digest is stale.")
    expected_key = payload_digest(
        _key_material(
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


def _record_installation(
    store: MemoryStore,
    *,
    entry_key: str,
    analysis: AtomizeAnalysisSession,
) -> None:
    path = _installation_path(store, analysis.uid)
    if path.parent.exists() and (not path.parent.is_dir() or path.parent.is_symlink()):
        raise StudyPrewarmRegistryError("Atomize prewarm receipt directory is unsafe.")
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(
        path,
        {
            "kind": "STUDY_ATOMIZE_PREWARM_INSTALLATION",
            "schema_version": 1,
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "entry_key": entry_key,
            "analysis_uid": analysis.uid,
            "analysis_digest": _analysis_digest(analysis),
        },
    )


def is_installed_atomize_prewarm(
    store: MemoryStore,
    analysis: AtomizeAnalysisSession,
) -> bool:
    path = _installation_path(store, analysis.uid)
    if not path.exists():
        return False
    if not path.is_file() or path.is_symlink():
        raise StudyPrewarmRegistryError("Atomize prewarm receipt is unsafe.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise StudyPrewarmRegistryError("Atomize prewarm receipt is invalid.") from error
    return bool(
        isinstance(value, dict)
        and value.get("kind") == "STUDY_ATOMIZE_PREWARM_INSTALLATION"
        and value.get("schema_version") == 1
        and value.get("analysis_uid") == analysis.uid
        and value.get("analysis_digest") == _analysis_digest(analysis)
    )


def install_declared_atomize_prewarms(
    *,
    store: MemoryStore,
    profile: ProfileEntry,
    registry_snapshot: ProfileRegistry,
    publish: bool = True,
) -> AtomizePrewarmInstallResult:
    """Install the exact tutorial seed into the production Atomize slot."""

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
    provider, model, reasoning = _configured_semantic_identity()
    installed: list[str] = []
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
        if (
            artifact.get("provider") != provider
            or artifact.get("model") != model
            or artifact.get("reasoning") != reasoning
        ):
            skipped += 1
            continue
        source = store.load_direct(analysis.context_name)
        current_description = store.load_direct(description["name"])
        if (
            current_description.uid != description["context_uid"]
            or context_record_digest(current_description)
            != description["context_digest"]
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
            opened = install_prepared_atomize_analysis(
                store=store,
                ctx=source,
                analysis=analysis,
                output_context_name="practice/source-atomized",
            )
            _record_installation(
                store,
                entry_key=entry.key,
                analysis=opened.analysis,
            )
            installed.append(opened.analysis.uid)
    return AtomizePrewarmInstallResult(
        declared=declared,
        installed=len(installed),
        skipped_configuration=skipped,
        analysis_uids=tuple(installed),
    )
