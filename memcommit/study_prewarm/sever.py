"""Declared exact Task 3 Sever reuse without exposing a hidden review row."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from memcommit.commands.granted_context import resolve_context_access
from memcommit.config import Config
from memcommit.context import Context
from memcommit.derived_policy import (
    authorize_analysis_save,
    authorize_combination,
    authorize_derived_transfer,
)
from memcommit.profile_config import ProfileEntry, ProfileRegistry, study_run_identity
from memcommit.sever import (
    SEVER_SCHEMA_VERSION,
    SeverContextBinding,
    SeverSession,
)
from memcommit.sever_provider import SEVER_PROVIDER_CONTRACT_VERSION
from memcommit.store import (
    MemoryStore,
    _write_json_atomic,
    context_record_digest,
    validate_context_name,
)
from memcommit.study_prewarm.compare import INSTALLATIONS_DIRECTORY_NAME
from memcommit.study_prewarm.registry import (
    StudyPrewarmRegistryError,
    load_artifact,
    load_registry,
    payload_digest,
)
from memcommit.study_prewarm.scope_equivalence import (
    ordered_scope_evidence_relation,
)


SEVER_ARTIFACT_KIND = "STUDY_SEVER_EXACT_PREWARM"
SEVER_ARTIFACT_SCHEMA_VERSION = 1
TASK = "task-3"
DESCRIPTION_NAME = "task-3/description"
SOURCE_NAME = "task-3/local/personal-memory"
CRITERIA_NAME = "task-3/local/guardrails"
OUTPUT_NAME = "task-3/participant/subtractive-first"


@dataclass(frozen=True)
class SeverPrewarmInstallResult:
    declared: int
    installed: int
    skipped_configuration: int
    entry_keys: tuple[str, ...]


@dataclass(frozen=True)
class SeverPrewarmMatch:
    """One complete candidate ledger rebound onto an unchanged source subset."""

    session: SeverSession
    origin: str


def _portable_session(session: SeverSession) -> SeverSession:
    """Keep semantic decisions but remove review and run-local state."""

    return replace(
        session,
        revision=1,
        state="REVIEWING",
        source=replace(session.source, granted=None),
        criteria=replace(session.criteria, granted=None),
        candidates=tuple(
            replace(candidate, selection="RECOMMENDED", custom_content="")
            for candidate in session.candidates
        ),
        application=None,
    )


def _description_identity(description: Context) -> dict[str, str]:
    return {
        "name": description.name,
        "context_uid": description.uid,
        "context_digest": context_record_digest(description),
    }


def _binding_identity(binding: SeverContextBinding) -> dict[str, object]:
    return {
        "root_uid": binding.root_uid,
        "root_name": binding.root_name,
        "frame_digest": binding.frame_digest,
        "include_descendants": binding.include_descendants,
        "excluded_query_context_names": list(binding.excluded_query_context_names),
    }


def _key_material(
    *,
    description: dict[str, str],
    session: SeverSession,
    provider: str,
    model: str,
    reasoning: str | None,
) -> dict[str, object]:
    return {
        "operation": "SEVER",
        "task": TASK,
        "provider": provider,
        "model": model,
        "reasoning": reasoning,
        "provider_contract_version": SEVER_PROVIDER_CONTRACT_VERSION,
        "sever_schema_version": SEVER_SCHEMA_VERSION,
        "task_description": description,
        "source": _binding_identity(session.source),
        "criteria": _binding_identity(session.criteria),
        # output_name is semantic provider input today, so it cannot be rebound
        # to an arbitrary destination without changing this exact contract.
        "output_name": session.output_name,
        "decision_digest": payload_digest(
            [candidate.to_dict() for candidate in session.candidates]
        ),
    }


def build_sever_prewarm_artifact(
    *,
    task_description: Context,
    session: SeverSession,
    provider: str,
    model: str,
    reasoning: str | None,
    offline_provider_seconds: float,
) -> tuple[str, dict[str, object]]:
    """Build one portable exact Task 3 Source × Criteria proposal."""

    portable = _portable_session(session)
    if (
        task_description.name != DESCRIPTION_NAME
        or portable.source.root_name != SOURCE_NAME
        or portable.criteria.root_name != CRITERIA_NAME
        or portable.output_name != OUTPUT_NAME
        or not portable.source.include_descendants
        or not portable.criteria.include_descendants
        or not portable.candidates
        or not isinstance(offline_provider_seconds, (int, float))
        or isinstance(offline_provider_seconds, bool)
        or offline_provider_seconds < 0
    ):
        raise StudyPrewarmRegistryError("Task 3 Sever prewarm basis is invalid.")
    description = _description_identity(task_description)
    material = _key_material(
        description=description,
        session=portable,
        provider=provider,
        model=model,
        reasoning=reasoning,
    )
    key = payload_digest(material)
    return key, {
        "kind": SEVER_ARTIFACT_KIND,
        "schema_version": SEVER_ARTIFACT_SCHEMA_VERSION,
        "key": key,
        **material,
        "offline_provider_seconds": float(offline_provider_seconds),
        "session_digest": payload_digest(portable.to_dict()),
        "session": portable.to_dict(),
    }


def _configured_semantic_identity() -> tuple[str, str | None, str | None]:
    config = Config()
    provider = config.semantic_provider()
    model = config.model_for_provider(provider)
    reasoning = config.codex_reasoning_effort() if provider == "codex_chatgpt" else None
    return provider, model, reasoning


def _validate_artifact(
    value: dict[str, object], *, entry_key: str
) -> tuple[SeverSession, dict[str, str]]:
    if (
        value.get("kind") != SEVER_ARTIFACT_KIND
        or value.get("schema_version") != SEVER_ARTIFACT_SCHEMA_VERSION
        or value.get("key") != entry_key
        or value.get("operation") != "SEVER"
        or value.get("task") != TASK
        or value.get("provider_contract_version") != SEVER_PROVIDER_CONTRACT_VERSION
        or value.get("sever_schema_version") != SEVER_SCHEMA_VERSION
    ):
        raise StudyPrewarmRegistryError("Declared Sever prewarm is invalid.")
    description = value.get("task_description")
    if (
        not isinstance(description, dict)
        or set(description) != {"name", "context_uid", "context_digest"}
        or not all(isinstance(item, str) for item in description.values())
    ):
        raise StudyPrewarmRegistryError("Sever task description identity is invalid.")
    try:
        session = SeverSession.from_dict(value.get("session"))
    except (TypeError, ValueError) as error:
        raise StudyPrewarmRegistryError("Declared Sever session is invalid.") from error
    if (
        session != _portable_session(session)
        or session.source.root_name != SOURCE_NAME
        or session.criteria.root_name != CRITERIA_NAME
        or session.output_name != OUTPUT_NAME
        or not session.source.include_descendants
        or not session.criteria.include_descendants
        or value.get("session_digest") != payload_digest(session.to_dict())
        or value.get("decision_digest")
        != payload_digest([candidate.to_dict() for candidate in session.candidates])
    ):
        raise StudyPrewarmRegistryError("Declared Sever session is stale.")
    provider = value.get("provider")
    model = value.get("model")
    reasoning = value.get("reasoning")
    if not isinstance(provider, str) or not isinstance(model, str) or (
        reasoning is not None and not isinstance(reasoning, str)
    ):
        raise StudyPrewarmRegistryError("Sever provider identity is invalid.")
    expected = payload_digest(
        _key_material(
            description=description,  # type: ignore[arg-type]
            session=session,
            provider=provider,
            model=model,
            reasoning=reasoning,
        )
    )
    if expected != entry_key:
        raise StudyPrewarmRegistryError("Sever prewarm key is stale.")
    return session, description  # type: ignore[return-value]


def _receipt_path(store: MemoryStore, entry_key: str) -> Path:
    return store.store_dir / INSTALLATIONS_DIRECTORY_NAME / f"sever-{entry_key}.json"


def _record_installation(
    store: MemoryStore,
    *,
    entry_key: str,
    source: SeverContextBinding,
    criteria: SeverContextBinding,
) -> None:
    path = _receipt_path(store, entry_key)
    if path.parent.exists() and (not path.parent.is_dir() or path.parent.is_symlink()):
        raise StudyPrewarmRegistryError("Sever prewarm receipt directory is unsafe.")
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(
        path,
        {
            "kind": "STUDY_SEVER_PREWARM_INSTALLATION",
            "schema_version": 1,
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "entry_key": entry_key,
            "source_frame_digest": source.frame_digest,
            "criteria_frame_digest": criteria.frame_digest,
        },
    )


def _receipt_matches(
    store: MemoryStore,
    *,
    entry_key: str,
    source: SeverContextBinding,
    criteria: SeverContextBinding,
) -> bool:
    path = _receipt_path(store, entry_key)
    if not path.exists():
        return False
    if not path.is_file() or path.is_symlink():
        raise StudyPrewarmRegistryError("Sever prewarm receipt is unsafe.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise StudyPrewarmRegistryError("Sever prewarm receipt is invalid.") from error
    return bool(
        isinstance(value, dict)
        and value.get("kind") == "STUDY_SEVER_PREWARM_INSTALLATION"
        and value.get("schema_version") == 1
        and value.get("entry_key") == entry_key
        and value.get("source_frame_digest") == source.frame_digest
        and value.get("criteria_frame_digest") == criteria.frame_digest
    )


def _semantic_binding_matches(
    prepared: SeverContextBinding, current: SeverContextBinding
) -> bool:
    return replace(prepared, granted=current.granted) == current


def _fresh_review(
    prepared: SeverSession,
    *,
    source: SeverContextBinding,
    criteria: SeverContextBinding,
) -> SeverSession:
    if not _semantic_binding_matches(prepared.source, source) or not _semantic_binding_matches(
        prepared.criteria, criteria
    ):
        raise StudyPrewarmRegistryError(
            "Declared Sever prewarm does not match current inputs."
        )
    session_uid = str(uuid.uuid4())
    candidates = tuple(
        replace(
            candidate,
            uid=str(uuid.uuid5(uuid.UUID(session_uid), candidate.source_memory_uid)),
            selection="RECOMMENDED",
            custom_content="",
        )
        for candidate in prepared.candidates
    )
    return replace(
        prepared,
        uid=session_uid,
        revision=1,
        state="REVIEWING",
        source=source,
        criteria=criteria,
        candidates=candidates,
        application=None,
    )


def _memory_evidence(binding: SeverContextBinding) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (memory.uid, memory.context_name, memory.content)
        for memory in binding.memories
    )


def _project_review(
    prepared: SeverSession,
    *,
    source: SeverContextBinding,
    criteria: SeverContextBinding,
) -> tuple[SeverSession, str] | None:
    """Filter decisions only when their complete semantic support survives."""

    source_relation = ordered_scope_evidence_relation(
        _memory_evidence(prepared.source),
        _memory_evidence(source),
    )
    criteria_relation = ordered_scope_evidence_relation(
        _memory_evidence(prepared.criteria),
        _memory_evidence(criteria),
    )
    if source_relation is None or criteria_relation is None or not source.memories:
        return None
    source_uids = {memory.uid for memory in source.memories}
    criterion_uids = {memory.uid for memory in criteria.memories}
    prepared_by_source = {
        candidate.source_memory_uid: candidate
        for candidate in prepared.candidates
    }
    source_by_uid = {memory.uid: memory for memory in source.memories}
    if not source_uids <= set(prepared_by_source):
        return None
    candidates = tuple(
        candidate
        if set(candidate.criterion_memory_uids) <= criterion_uids
        else replace(
            candidate,
            recommendation="KEEP_AS_WRITTEN",
            proposed_content=source_by_uid[source_uid].content,
            rationale=(
                "The requested Criteria subset removes prepared support for "
                "this transformation, so the Source is preserved as written."
            ),
            criterion_memory_uids=(),
        )
        for source_uid in (memory.uid for memory in source.memories)
        for candidate in (prepared_by_source[source_uid],)
    )
    session_uid = str(uuid.uuid4())
    candidates = tuple(
        replace(
            candidate,
            uid=str(uuid.uuid5(uuid.UUID(session_uid), candidate.source_memory_uid)),
            selection="RECOMMENDED",
            custom_content="",
        )
        for candidate in candidates
    )
    summary = prepared.applied_summary
    if summary is not None and (
        not set(summary.source_memory_uids) <= source_uids
        or not set(summary.criterion_memory_uids) <= criterion_uids
    ):
        summary = None
    projected = replace(
        prepared,
        uid=session_uid,
        revision=1,
        state="REVIEWING",
        source=source,
        criteria=criteria,
        overview=(
            prepared.overview
            if source_relation == criteria_relation == "EQUAL"
            else "Projected from the declared Sever basis; every displayed "
            "Source decision retains all of its cited Criteria support."
        ),
        candidates=candidates,
        applied_summary=summary,
        application=None,
    )
    # Round-trip through validation so projection can never publish partial
    # Source coverage or dangling Criteria references.
    validated = SeverSession.from_dict(projected.to_dict())
    return validated, (
        "EQUIVALENT_SCOPE_PREWARM"
        if source_relation == criteria_relation == "EQUAL"
        else "PROJECTED_PREWARM"
    )
def _validate_description(store: MemoryStore, description: dict[str, str]) -> None:
    current = store.load_direct(description["name"])
    if (
        current.uid != description["context_uid"]
        or context_record_digest(current) != description["context_digest"]
    ):
        raise StudyPrewarmRegistryError(
            "Task 3 description changed after Sever was prepared."
        )


def install_declared_sever_prewarms(
    *,
    store: MemoryStore,
    profile: ProfileEntry,
    registry_snapshot: ProfileRegistry,
    publish: bool = True,
) -> SeverPrewarmInstallResult:
    """Validate exact Sever inputs and install only a hidden lookup receipt."""

    registry = load_registry(store.store_dir)
    if registry is None:
        return SeverPrewarmInstallResult(0, 0, 0, ())
    identity = study_run_identity(profile)
    if identity is None or identity.role != "PARTICIPANT":
        raise StudyPrewarmRegistryError("Sever prewarm requires a participant Study Profile.")
    if registry.baseline_profile_uid != identity.baseline_profile_uid:
        raise StudyPrewarmRegistryError("Sever prewarm belongs to a different baseline.")
    provider_identity = _configured_semantic_identity()
    declared = skipped = 0
    installed: list[str] = []
    for entry in registry.entries:
        if not entry.enabled or entry.operation != "SEVER":
            continue
        declared += 1
        artifact = load_artifact(store.store_dir, entry)
        prepared, description = _validate_artifact(artifact, entry_key=entry.key)
        if (
            artifact.get("provider"),
            artifact.get("model"),
            artifact.get("reasoning"),
        ) != provider_identity:
            skipped += 1
            continue
        _validate_description(store, description)
        current_name = store.current_context_name()
        source_access = resolve_context_access(
            store,
            SOURCE_NAME,
            current_name=current_name,
            required_permission="READ",
            registry=registry_snapshot,
        )
        criteria_access = resolve_context_access(
            store,
            CRITERIA_NAME,
            current_name=current_name,
            required_permission="READ",
            registry=registry_snapshot,
        )
        output_access = _local_output_access(store, OUTPUT_NAME)
        authorize_combination((source_access, criteria_access))
        authorize_derived_transfer(source_access, output_access)
        authorize_derived_transfer(criteria_access, output_access)
        authorize_analysis_save((source_access, criteria_access), retention="RETAINED")
        # Import lazily so the command can independently consult this module at
        # runtime without a module-import cycle.
        from memcommit.commands.sever import _capture_binding

        source = _capture_binding(source_access, include_descendants=True)
        criteria = _capture_binding(criteria_access, include_descendants=True)
        _fresh_review(prepared, source=source, criteria=criteria)
        if publish:
            _record_installation(
                store,
                entry_key=entry.key,
                source=source,
                criteria=criteria,
            )
            installed.append(entry.key)
    return SeverPrewarmInstallResult(
        declared, len(installed), skipped, tuple(installed)
    )


def _local_output_access(store: MemoryStore, name: str):
    # Kept local to avoid broadening the public Context locator contract for a
    # require-new output name.
    from memcommit.commands.granted_context import ContextAccess

    validate_context_name(name)
    if store.context_exists(name):
        raise StudyPrewarmRegistryError(
            f"Sever prewarm output Context {name!r} already exists."
        )
    return ContextAccess(
        store=store,
        context_name=name,
        display_name=name,
        attachment_name=None,
        permission="CREATE",
    )


def find_installed_exact_sever_prewarm(
    *,
    store: MemoryStore,
    source: SeverContextBinding,
    criteria: SeverContextBinding,
    output_name: str,
) -> SeverSession | None:
    """Return a fresh exact review, or ``None`` so the caller runs live."""

    registry = load_registry(store.store_dir)
    if registry is None:
        return None
    provider_identity = _configured_semantic_identity()
    matches: list[SeverSession] = []
    for entry in registry.entries:
        if not entry.enabled or entry.operation != "SEVER":
            continue
        artifact = load_artifact(store.store_dir, entry)
        prepared, description = _validate_artifact(artifact, entry_key=entry.key)
        if (
            artifact.get("provider"),
            artifact.get("model"),
            artifact.get("reasoning"),
        ) != provider_identity or prepared.output_name != output_name:
            continue
        try:
            _validate_description(store, description)
        except StudyPrewarmRegistryError:
            # Post-setup task edits are ordinary cache misses. The live path
            # remains available against the complete current frame.
            continue
        if not _receipt_matches(
            store,
            entry_key=entry.key,
            source=source,
            criteria=criteria,
        ):
            continue
        if not _semantic_binding_matches(
            prepared.source, source
        ) or not _semantic_binding_matches(prepared.criteria, criteria):
            continue
        matches.append(_fresh_review(prepared, source=source, criteria=criteria))
    if len(matches) > 1:
        raise StudyPrewarmRegistryError(
            "Multiple declared Sever prewarms match the same frozen request."
        )
    return matches[0] if matches else None


def find_installed_projectable_sever_prewarm(
    *,
    store: MemoryStore,
    source: SeverContextBinding,
    criteria: SeverContextBinding,
    output_name: str,
) -> SeverPrewarmMatch | None:
    """Return an equal or support-preserving subset review without inference."""

    registry = load_registry(store.store_dir)
    if registry is None or not (
        source.root_name.startswith(TASK + "/")
        and criteria.root_name.startswith(TASK + "/")
    ):
        return None
    provider_identity = _configured_semantic_identity()
    matches: list[SeverPrewarmMatch] = []
    for entry in registry.entries:
        if not entry.enabled or entry.operation != "SEVER":
            continue
        artifact = load_artifact(store.store_dir, entry)
        prepared, description = _validate_artifact(artifact, entry_key=entry.key)
        if (
            (
                artifact.get("provider"),
                artifact.get("model"),
                artifact.get("reasoning"),
            )
            != provider_identity
            or prepared.output_name != output_name
        ):
            continue
        try:
            _validate_description(store, description)
            from memcommit.commands.sever import _capture_binding

            current_name = store.current_context_name()
            canonical_source = _capture_binding(
                resolve_context_access(
                    store,
                    SOURCE_NAME,
                    current_name=current_name,
                    required_permission="READ",
                ),
                include_descendants=True,
            )
            canonical_criteria = _capture_binding(
                resolve_context_access(
                    store,
                    CRITERIA_NAME,
                    current_name=current_name,
                    required_permission="READ",
                ),
                include_descendants=True,
            )
        except (OSError, StudyPrewarmRegistryError, ValueError):
            continue
        if not _receipt_matches(
            store,
            entry_key=entry.key,
            source=canonical_source,
            criteria=canonical_criteria,
        ):
            continue
        projected = _project_review(
            prepared,
            source=source,
            criteria=criteria,
        )
        if projected is None:
            continue
        session, origin = projected
        matches.append(SeverPrewarmMatch(session=session, origin=origin))
    if len(matches) > 1:
        raise StudyPrewarmRegistryError(
            "Multiple declared Sever prewarms match the same frozen request."
        )
    return matches[0] if matches else None


def installed_sever_request_origin(
    *,
    store: MemoryStore,
    source: SeverContextBinding,
    criteria: SeverContextBinding,
    output_name: str,
) -> str | None:
    match = find_installed_projectable_sever_prewarm(
        store=store,
        source=source,
        criteria=criteria,
        output_name=output_name,
    )
    return match.origin if match is not None else None


def is_installed_exact_sever_request(
    *,
    store: MemoryStore,
    source: SeverContextBinding,
    criteria: SeverContextBinding,
    output_name: str,
) -> bool:
    """Report whether this already-frozen request used the declared exact row."""

    return find_installed_exact_sever_prewarm(
        store=store,
        source=source,
        criteria=criteria,
        output_name=output_name,
    ) is not None
