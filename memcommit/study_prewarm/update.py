"""Setup-time installation of the exact Task 1 directional Update plan."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from memcommit.commands.granted_context import (
    GrantedReadStore,
    freeze_granted_update_target,
    resolve_context_access,
)
from memcommit.config import Config
from memcommit.context import Context
from memcommit.context_targeting.loading import load_context_scope
from memcommit.derived_policy import authorize_derived_transfer
from memcommit.profile_config import (
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    study_run_identity,
)
from memcommit.store import MemoryStore, _write_json_atomic, context_record_digest
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
from memcommit.update import (
    UPDATE_PROVIDER_CONTRACT_VERSION,
    UPDATE_SCHEMA_VERSION,
    GrantedUpdateTarget,
    UpdateSession,
    AddOperation,
    EditOperation,
    RemoveOperation,
    collect_update_inputs,
    operation_digest,
    session_matches,
)


UPDATE_ARTIFACT_KIND = "STUDY_UPDATE_EXACT_PREWARM"
UPDATE_ARTIFACT_SCHEMA_VERSION = 1
TASK = "task-1"
SOURCE_NAME = "task-1/participant/construction-updates"
TARGET_NAME = "task-1/campus-wiki"


@dataclass(frozen=True)
class UpdatePrewarmInstallResult:
    declared: int
    installed: int
    skipped_configuration: int
    session_uids: tuple[str, ...]


@dataclass(frozen=True)
class EquivalentUpdatePrewarmMatch:
    """One Update basis rebound or projected onto the current scopes."""

    entry_key: str
    session: UpdateSession
    prepared_source_name: str
    origin: str = "EQUIVALENT_SCOPE_PREWARM"


def _portable_session(session: UpdateSession) -> UpdateSession:
    # Grant/profile identities are run-local. Only the validated semantic plan
    # crosses runs; installation freezes the current bindings again.
    return replace(
        session,
        status="impact",
        granted_source=None,
        granted_target=None,
        application=None,
    )


def _description_identity(description: Context) -> dict[str, str]:
    return {
        "name": description.name,
        "context_uid": description.uid,
        "context_digest": context_record_digest(description),
    }


def _key_material(
    *,
    description: dict[str, str],
    session: UpdateSession,
    provider: str,
    model: str,
    reasoning: str | None,
) -> dict[str, object]:
    return {
        "operation": "UPDATE",
        "task": TASK,
        "provider": provider,
        "model": model,
        "reasoning": reasoning,
        "provider_contract_version": UPDATE_PROVIDER_CONTRACT_VERSION,
        "update_schema_version": UPDATE_SCHEMA_VERSION,
        "task_description": description,
        "source": {
            "uid": session.source_uid,
            "name": session.source_name,
            "digest": session.source_digest,
            "contexts": [item.to_dict() for item in session.source_contexts],
            "include_descendants": session.source_include_descendants,
        },
        "target": {
            "uid": session.target_uid,
            "name": session.target_name,
            "digest": session.target_digest,
            "contexts": [item.to_dict() for item in session.target_contexts],
            "include_descendants": session.target_include_descendants,
        },
        "operation_digest": operation_digest(session.operations),
    }


def build_update_prewarm_artifact(
    *,
    task_description: Context,
    session: UpdateSession,
    provider: str,
    model: str,
    reasoning: str | None,
    offline_provider_seconds: float,
) -> tuple[str, dict[str, object]]:
    """Build one portable exact Task 1 Update artifact."""

    portable = _portable_session(session)
    if (
        task_description.name != "task-1/description"
        or portable.source_name != SOURCE_NAME
        or portable.target_name != TARGET_NAME
        or not portable.source_include_descendants
        or not portable.target_include_descendants
        or not portable.operations
        or not isinstance(offline_provider_seconds, (int, float))
        or isinstance(offline_provider_seconds, bool)
        or offline_provider_seconds < 0
    ):
        raise StudyPrewarmRegistryError("Task 1 Update prewarm basis is invalid.")
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
        "kind": UPDATE_ARTIFACT_KIND,
        "schema_version": UPDATE_ARTIFACT_SCHEMA_VERSION,
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


def _validate_artifact(value: dict[str, object], *, entry_key: str) -> tuple[UpdateSession, dict[str, str]]:
    if (
        value.get("kind") != UPDATE_ARTIFACT_KIND
        or value.get("schema_version") != UPDATE_ARTIFACT_SCHEMA_VERSION
        or value.get("key") != entry_key
        or value.get("operation") != "UPDATE"
        or value.get("task") != TASK
        or value.get("provider_contract_version") != UPDATE_PROVIDER_CONTRACT_VERSION
        or value.get("update_schema_version") != UPDATE_SCHEMA_VERSION
    ):
        raise StudyPrewarmRegistryError("Declared Update prewarm is invalid.")
    description = value.get("task_description")
    if (
        not isinstance(description, dict)
        or set(description) != {"name", "context_uid", "context_digest"}
        or not all(isinstance(item, str) for item in description.values())
    ):
        raise StudyPrewarmRegistryError("Update task description identity is invalid.")
    try:
        session = UpdateSession.from_dict(value.get("session"))
    except ValueError as error:
        raise StudyPrewarmRegistryError("Declared Update session is invalid.") from error
    if (
        session != _portable_session(session)
        or session.source_name != SOURCE_NAME
        or session.target_name != TARGET_NAME
        or not session.source_include_descendants
        or not session.target_include_descendants
        or not session.operations
        or value.get("session_digest") != payload_digest(session.to_dict())
        or value.get("operation_digest") != operation_digest(session.operations)
    ):
        raise StudyPrewarmRegistryError("Declared Update session is stale.")
    provider = value.get("provider")
    model = value.get("model")
    reasoning = value.get("reasoning")
    if not isinstance(provider, str) or not isinstance(model, str) or (
        reasoning is not None and not isinstance(reasoning, str)
    ):
        raise StudyPrewarmRegistryError("Update provider identity is invalid.")
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
        raise StudyPrewarmRegistryError("Update prewarm key is stale.")
    return session, description  # type: ignore[return-value]


def _installation_path(store: MemoryStore, session_uid: str) -> Path:
    return store.store_dir / INSTALLATIONS_DIRECTORY_NAME / f"update-{session_uid}.json"


def _record_installation(store: MemoryStore, *, entry_key: str, session: UpdateSession) -> None:
    path = _installation_path(store, session.uid)
    if path.parent.exists() and (not path.parent.is_dir() or path.parent.is_symlink()):
        raise StudyPrewarmRegistryError("Update prewarm receipt directory is unsafe.")
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(
        path,
        {
            "kind": "STUDY_UPDATE_PREWARM_INSTALLATION",
            "schema_version": 1,
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "entry_key": entry_key,
            "session_uid": session.uid,
            "operation_digest": operation_digest(session.operations),
        },
    )


def is_installed_update_prewarm(store: MemoryStore, session: UpdateSession) -> bool:
    path = _installation_path(store, session.uid)
    if not path.exists():
        return False
    if not path.is_file() or path.is_symlink():
        raise StudyPrewarmRegistryError("Update prewarm receipt is unsafe.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise StudyPrewarmRegistryError("Update prewarm receipt is invalid.") from error
    return bool(
        isinstance(value, dict)
        and value.get("kind") == "STUDY_UPDATE_PREWARM_INSTALLATION"
        and value.get("schema_version") == 1
        and value.get("session_uid") == session.uid
        and value.get("operation_digest") == operation_digest(session.operations)
    )


def record_equivalent_update_prewarm(
    store: MemoryStore,
    *,
    entry_key: str,
    session: UpdateSession,
    prepared_source_name: str,
) -> None:
    path = _installation_path(store, session.uid)
    if path.parent.exists() and (not path.parent.is_dir() or path.parent.is_symlink()):
        raise StudyPrewarmRegistryError("Update prewarm receipt directory is unsafe.")
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(
        path,
        {
            "kind": "STUDY_UPDATE_EQUIVALENT_SCOPE_PREWARM",
            "schema_version": 1,
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "entry_key": entry_key,
            "session_uid": session.uid,
            "operation_digest": operation_digest(session.operations),
            "prepared_source_name": prepared_source_name,
            "current_source_name": session.source_name,
            "source_digest": session.source_digest,
            "target_uid": session.target_uid,
            "target_name": session.target_name,
            "target_digest": session.target_digest,
        },
    )


def record_projected_update_prewarm(
    store: MemoryStore,
    *,
    entry_key: str,
    session: UpdateSession,
    prepared_source_name: str,
) -> None:
    """Retain the declared origin of one support-preserving subset plan."""

    path = _installation_path(store, session.uid)
    if path.parent.exists() and (not path.parent.is_dir() or path.parent.is_symlink()):
        raise StudyPrewarmRegistryError("Update prewarm receipt directory is unsafe.")
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(
        path,
        {
            "kind": "STUDY_UPDATE_PROJECTED_PREWARM",
            "schema_version": 1,
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "entry_key": entry_key,
            "session_uid": session.uid,
            "operation_digest": operation_digest(session.operations),
            "prepared_source_name": prepared_source_name,
            "current_source_name": session.source_name,
            "source_digest": session.source_digest,
            "target_uid": session.target_uid,
            "target_name": session.target_name,
            "target_digest": session.target_digest,
        },
    )


def installed_update_prewarm_origin(
    store: MemoryStore,
    session: UpdateSession,
) -> str | None:
    if is_installed_update_prewarm(store, session):
        return "EXACT_PREWARM"
    path = _installation_path(store, session.uid)
    if not path.exists():
        return None
    if not path.is_file() or path.is_symlink():
        raise StudyPrewarmRegistryError("Update prewarm receipt is unsafe.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise StudyPrewarmRegistryError("Update prewarm receipt is invalid.") from error
    if not isinstance(value, dict):
        return None
    if (
        value.get("kind") == "STUDY_UPDATE_EQUIVALENT_SCOPE_PREWARM"
        and value.get("schema_version") == 1
        and value.get("session_uid") == session.uid
        and value.get("operation_digest") == operation_digest(session.operations)
        and value.get("current_source_name") == session.source_name
        and value.get("source_digest") == session.source_digest
        and value.get("target_uid") == session.target_uid
        and value.get("target_name") == session.target_name
        and value.get("target_digest") == session.target_digest
    ):
        return "EQUIVALENT_SCOPE_PREWARM"
    if (
        value.get("kind") == "STUDY_UPDATE_PROJECTED_PREWARM"
        and value.get("schema_version") == 1
        and value.get("session_uid") == session.uid
        and value.get("operation_digest") == operation_digest(session.operations)
        and value.get("current_source_name") == session.source_name
        and value.get("source_digest") == session.source_digest
        and value.get("target_uid") == session.target_uid
        and value.get("target_name") == session.target_name
        and value.get("target_digest") == session.target_digest
    ):
        return "PROJECTED_PREWARM"
    return None


def _rebind_portable_session(
    prepared: UpdateSession,
    *,
    source: Context,
    target: Context,
    granted_source: GrantedUpdateTarget | None,
    granted_target: GrantedUpdateTarget | None,
) -> UpdateSession:
    """Bind one semantic payload to this run's regenerated graph fingerprints."""

    inputs = collect_update_inputs(source, target)
    if (
        prepared.source_uid != source.uid
        or prepared.source_name != source.name
        or prepared.source_digest != inputs.source_digest
        or prepared.target_uid != target.uid
        or prepared.target_name != target.name
        or prepared.target_digest != inputs.target_digest
    ):
        raise StudyPrewarmRegistryError(
            "Declared Update prewarm does not match current inputs."
        )
    source_refs = {
        (
            candidate.context_uid,
            candidate.context_name,
            candidate.memory_uid,
            candidate.reference.content_digest,
        )
        for candidate in inputs.source_candidates
    }
    target_contexts = {
        (candidate.context_uid, candidate.context_name)
        for candidate in inputs.target_contexts
    }
    target_memories = {
        (candidate.context_uid, candidate.context_name, candidate.memory_uid): candidate.content
        for candidate in inputs.target_memories
    }
    added_uids: set[tuple[str, str]] = set()
    for operation in prepared.operations:
        owner = (operation.owner_context_uid, operation.owner_context_name)
        if owner not in target_contexts or any(
            (
                ref.context_uid,
                ref.context_name,
                ref.memory_uid,
                ref.content_digest,
            )
            not in source_refs
            for ref in operation.source_refs
        ):
            raise StudyPrewarmRegistryError("Update operation provenance is stale.")
        if isinstance(operation, (EditOperation, RemoveOperation)):
            if target_memories.get((*owner, operation.memory_uid)) != operation.old_content:
                raise StudyPrewarmRegistryError("Update target operation is stale.")
        elif isinstance(operation, AddOperation):
            identity = (operation.owner_context_uid, operation.memory_uid)
            if identity in added_uids or (*owner, operation.memory_uid) in target_memories:
                raise StudyPrewarmRegistryError("Update addition identity is stale.")
            added_uids.add(identity)
    # Context fingerprints include run-local graph bindings. The exhaustive
    # input digests above establish identical semantic payloads; publish the
    # current fingerprints so Update's ordinary reuse and apply checks remain
    # authoritative after setup.
    return replace(
        prepared,
        source_contexts=inputs.source_contexts,
        target_contexts=inputs.target_context_fingerprints,
        granted_source=granted_source,
        granted_target=granted_target,
    )


def _source_evidence(inputs) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            candidate.context_uid,
            candidate.context_name,
            candidate.memory_uid,
            candidate.content,
        )
        for candidate in inputs.source_candidates
    )


def _target_memory_evidence(inputs) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            candidate.context_uid,
            candidate.context_name,
            candidate.memory_uid,
            candidate.content,
        )
        for candidate in inputs.target_memories
    )


def _effective_target_context_evidence(
    inputs,
    *,
    prepared_owner_uids: frozenset[str],
) -> tuple[tuple[str, str], ...]:
    """Ignore empty locator wrappers while retaining every writable owner.

    Update exposes Contexts as ADD destinations.  A wrapper is transparent
    only when it owns no Memory and was not an owner in the prepared action
    ledger; a nonempty or action-owning Context remains semantic evidence.
    """

    occupied = {memory.context_uid for memory in inputs.target_memories}
    effective = occupied | set(prepared_owner_uids)
    return tuple(
        (candidate.context_uid, candidate.context_name)
        for candidate in inputs.target_contexts
        if candidate.context_uid in effective
    )


def _project_update_session(
    prepared: UpdateSession,
    *,
    basis_inputs,
    source: Context,
    target: Context,
    source_include_descendants: bool,
    target_include_descendants: bool,
    granted_source: GrantedUpdateTarget | None,
    granted_target: GrantedUpdateTarget | None,
) -> tuple[UpdateSession, str] | None:
    """Rebind equal scopes or filter a declared plan onto unchanged subsets."""

    current_inputs = collect_update_inputs(source, target)
    current_source_evidence = _source_evidence(current_inputs)
    prepared_source_evidence = _source_evidence(basis_inputs)
    source_relation = ordered_scope_evidence_relation(
        prepared_source_evidence,
        current_source_evidence,
    )
    if source_relation is None:
        return None

    prepared_owner_uids = frozenset(
        operation.owner_context_uid for operation in prepared.operations
    )
    prepared_target_contexts = _effective_target_context_evidence(
        basis_inputs,
        prepared_owner_uids=prepared_owner_uids,
    )
    current_target_contexts = _effective_target_context_evidence(
        current_inputs,
        prepared_owner_uids=prepared_owner_uids,
    )
    target_context_relation = ordered_scope_evidence_relation(
        prepared_target_contexts,
        current_target_contexts,
    )
    target_memory_relation = ordered_scope_evidence_relation(
        _target_memory_evidence(basis_inputs),
        _target_memory_evidence(current_inputs),
    )
    if target_context_relation is None or target_memory_relation is None:
        return None

    current_source_refs = {
        (
            candidate.context_uid,
            candidate.context_name,
            candidate.memory_uid,
            candidate.reference.content_digest,
        )
        for candidate in current_inputs.source_candidates
    }
    current_target_context_set = set(current_target_contexts)
    current_target_memories = {
        (
            candidate.context_uid,
            candidate.context_name,
            candidate.memory_uid,
            candidate.content,
        )
        for candidate in current_inputs.target_memories
    }
    operations = tuple(
        operation
        for operation in prepared.operations
        if (
            (operation.owner_context_uid, operation.owner_context_name)
            in current_target_context_set
            and all(
                (
                    reference.context_uid,
                    reference.context_name,
                    reference.memory_uid,
                    reference.content_digest,
                )
                in current_source_refs
                for reference in operation.source_refs
            )
            and (
                isinstance(operation, AddOperation)
                or (
                    operation.owner_context_uid,
                    operation.owner_context_name,
                    operation.memory_uid,
                    operation.old_content,
                )
                in current_target_memories
            )
        )
    )
    relation = (
        "EQUAL"
        if source_relation == target_context_relation == target_memory_relation == "EQUAL"
        else "SUBSET"
    )
    projected = replace(
        prepared,
        uid=str(uuid.uuid4()),
        status="impact",
        created_at=datetime.now(timezone.utc).isoformat(),
        source_uid=source.uid,
        source_name=source.name,
        source_digest=current_inputs.source_digest,
        source_contexts=current_inputs.source_contexts,
        target_uid=target.uid,
        target_name=target.name,
        target_digest=current_inputs.target_digest,
        target_contexts=current_inputs.target_context_fingerprints,
        operations=operations,
        source_include_descendants=source_include_descendants,
        target_include_descendants=target_include_descendants,
        granted_source=granted_source,
        granted_target=granted_target,
        application=None,
    )
    if not session_matches(
        projected,
        source,
        target,
        granted_source=granted_source,
        granted_target=granted_target,
    ):
        return None
    return projected, relation


def find_installed_projectable_update_prewarm(
    *,
    store: MemoryStore,
    source: Context,
    target: Context,
    source_include_descendants: bool,
    target_include_descendants: bool,
    granted_source: GrantedUpdateTarget | None,
    granted_target: GrantedUpdateTarget | None,
    registry_snapshot: ProfileRegistry | None = None,
) -> EquivalentUpdatePrewarmMatch | None:
    """Find one installed Task 1 plan for an equal or unchanged subset scope."""

    registry = load_registry(store.store_dir)
    if registry is None:
        return None
    if (
        not source.name.startswith(TASK + "/")
        or not target.name.startswith(TASK + "/")
    ):
        return None
    profile_registry = registry_snapshot or load_profile_registry()
    provider, model, reasoning = _configured_semantic_identity()
    matches: list[EquivalentUpdatePrewarmMatch] = []
    for entry in registry.entries:
        if not entry.enabled or entry.operation != "UPDATE":
            continue
        artifact = load_artifact(store.store_dir, entry)
        prepared, description = _validate_artifact(artifact, entry_key=entry.key)
        if (
            artifact.get("provider"),
            artifact.get("model"),
            artifact.get("reasoning"),
        ) != (provider, model, reasoning):
            continue
        try:
            current_description = store.load_direct(description["name"])
            if (
                current_description.uid != description["context_uid"]
                or context_record_digest(current_description)
                != description["context_digest"]
            ):
                continue
            source_access = resolve_context_access(
                store,
                SOURCE_NAME,
                current_name=store.current_context_name(),
                required_permission="READ",
                registry=profile_registry,
            )
            target_access = resolve_context_access(
                store,
                TARGET_NAME,
                current_name=store.current_context_name(),
                required_permission="READ",
                registry=profile_registry,
            )
            exact_source_store = (
                GrantedReadStore(source_access, registry=profile_registry)
                if source_access.is_granted
                else store
            )
            exact_target_store = (
                GrantedReadStore(target_access, registry=profile_registry)
                if target_access.is_granted
                else store
            )
            exact_source = load_context_scope(
                exact_source_store,
                source_access.display_name
                if source_access.is_granted
                else source_access.context_name,
                include_descendants=True,
            )
            exact_target = load_context_scope(
                exact_target_store,
                target_access.display_name
                if target_access.is_granted
                else target_access.context_name,
                include_descendants=True,
            )
            canonical = _rebind_portable_session(
                prepared,
                source=exact_source,
                target=exact_target,
                granted_source=(
                    freeze_granted_update_target(source_access)
                    if source_access.is_granted
                    else None
                ),
                granted_target=(
                    freeze_granted_update_target(target_access)
                    if target_access.is_granted
                    else None
                ),
            )
            if not is_installed_update_prewarm(store, canonical):
                continue
            projected = _project_update_session(
                canonical,
                basis_inputs=collect_update_inputs(exact_source, exact_target),
                source=source,
                target=target,
                source_include_descendants=source_include_descendants,
                target_include_descendants=target_include_descendants,
                granted_source=granted_source,
                granted_target=granted_target,
            )
            if projected is None:
                continue
            rebound, relation = projected
        except (OSError, StudyPrewarmRegistryError, ValueError):
            continue
        matches.append(
            EquivalentUpdatePrewarmMatch(
                entry_key=entry.key,
                session=rebound,
                prepared_source_name=canonical.source_name,
                origin=(
                    "EQUIVALENT_SCOPE_PREWARM"
                    if relation == "EQUAL"
                    else "PROJECTED_PREWARM"
                ),
            )
        )
    if len(matches) > 1:
        raise StudyPrewarmRegistryError(
            "Multiple declared Update prewarms match the same frozen request."
        )
    return matches[0] if matches else None


def find_installed_equivalent_update_prewarm(
    *,
    store: MemoryStore,
    source: Context,
    target: Context,
    granted_source: GrantedUpdateTarget | None,
    granted_target: GrantedUpdateTarget | None,
    registry_snapshot: ProfileRegistry | None = None,
) -> EquivalentUpdatePrewarmMatch | None:
    """Compatibility wrapper retaining the former equal-scope result."""

    match = find_installed_projectable_update_prewarm(
        store=store,
        source=source,
        target=target,
        source_include_descendants=True,
        target_include_descendants=True,
        granted_source=granted_source,
        granted_target=granted_target,
        registry_snapshot=registry_snapshot,
    )
    return (
        match
        if match is not None and match.origin == "EQUIVALENT_SCOPE_PREWARM"
        else None
    )


def install_declared_update_prewarms(
    *,
    store: MemoryStore,
    profile: ProfileEntry,
    registry_snapshot: ProfileRegistry,
    publish: bool = True,
) -> UpdatePrewarmInstallResult:
    """Install the exact Task 1 proposal into Update's ordinary Impact slot."""

    registry = load_registry(store.store_dir)
    if registry is None:
        return UpdatePrewarmInstallResult(0, 0, 0, ())
    identity = study_run_identity(profile)
    if identity is None or identity.role != "PARTICIPANT":
        raise StudyPrewarmRegistryError("Update prewarm requires a participant Study Profile.")
    if registry.baseline_profile_uid != identity.baseline_profile_uid:
        raise StudyPrewarmRegistryError("Update prewarm belongs to a different baseline.")
    provider, model, reasoning = _configured_semantic_identity()
    declared = skipped = 0
    installed: list[str] = []
    for entry in registry.entries:
        if not entry.enabled or entry.operation != "UPDATE":
            continue
        declared += 1
        artifact = load_artifact(store.store_dir, entry)
        prepared, description = _validate_artifact(artifact, entry_key=entry.key)
        if (artifact.get("provider"), artifact.get("model"), artifact.get("reasoning")) != (provider, model, reasoning):
            skipped += 1
            continue
        current_description = store.load_direct(description["name"])
        if (
            current_description.uid != description["context_uid"]
            or context_record_digest(current_description) != description["context_digest"]
        ):
            raise StudyPrewarmRegistryError("Task 1 description changed after Update was prepared.")
        source_access = resolve_context_access(
            store, SOURCE_NAME, current_name=store.current_context_name(),
            required_permission="READ", registry=registry_snapshot,
        )
        target_access = resolve_context_access(
            store, TARGET_NAME, current_name=store.current_context_name(),
            required_permission="READ", registry=registry_snapshot,
        )
        authorize_derived_transfer(source_access, target_access)
        source_store = GrantedReadStore(source_access, registry=registry_snapshot) if source_access.is_granted else store
        target_store = GrantedReadStore(target_access, registry=registry_snapshot) if target_access.is_granted else store
        source = load_context_scope(source_store, source_access.display_name if source_access.is_granted else source_access.context_name, include_descendants=True)
        target = load_context_scope(target_store, target_access.display_name if target_access.is_granted else target_access.context_name, include_descendants=True)
        current = _rebind_portable_session(
            prepared,
            source=source,
            target=target,
            granted_source=freeze_granted_update_target(source_access) if source_access.is_granted else None,
            granted_target=freeze_granted_update_target(target_access) if target_access.is_granted else None,
        )
        if not session_matches(
            current, source, target,
            granted_source=current.granted_source,
            granted_target=current.granted_target,
        ):
            raise StudyPrewarmRegistryError("Declared Update prewarm does not match current inputs.")
        if publish:
            store.save_impact_plan(current)
            _record_installation(store, entry_key=entry.key, session=current)
            installed.append(current.uid)
    return UpdatePrewarmInstallResult(declared, len(installed), skipped, tuple(installed))
