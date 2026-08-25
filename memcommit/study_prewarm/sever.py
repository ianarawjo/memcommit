"""Declared exact Task 3 Sever reuse without exposing a hidden review row."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from memcommit.authority.access import ContextAccess, resolve_context_access
from memcommit.config import Config
from memcommit.infrastructure.providers.policy import (
    resolve_operation_provider_policy,
)
from memcommit.context import Context
from memcommit.context_naming import validate_portable_context_name
from memcommit.derived_policy import (
    authorize_analysis_save,
    authorize_combination,
    authorize_derived_transfer,
)
from memcommit.profile_config import ProfileEntry, ProfileRegistry, study_run_identity
from memcommit.operations.sever.model import (
    SEVER_SCHEMA_VERSION,
    SeverContextBinding,
    SeverSession,
)
from memcommit.operations.sever.provider import SEVER_PROVIDER_CONTRACT_VERSION
from memcommit.store import (
    MemoryStore,
    _write_json_atomic,
    context_record_digest,
)
from memcommit.study_prewarm.installations import (
    INSTALLATIONS_DIRECTORY_NAME,
    declared_artifact_available,
    record_declared_installation,
)
from memcommit.study_prewarm.registry import (
    StudyPrewarmRegistryError,
    load_artifact,
    load_registry,
    payload_digest,
)
from memcommit.study_prewarm.quality import (
    SemanticIdentity,
    highest_quality_candidates,
    prewarm_quality_satisfies,
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
    """One complete candidate ledger rebound onto an exact whole request."""

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
    """Build one portable exact Task 3 whole-Source × whole-Criteria proposal."""

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
    resolved = resolve_operation_provider_policy(
        "sever",
        config=Config(),
        mode="STUDY_PARTICIPANT",
    )
    return resolved.provider_id, resolved.model, resolved.reasoning_effort


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
    if (
        not isinstance(provider, str)
        or not isinstance(model, str)
        or (reasoning is not None and not isinstance(reasoning, str))
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


def _installation_evidence(
    source: SeverContextBinding,
    criteria: SeverContextBinding,
) -> dict[str, str]:
    return {
        "source_frame_digest": source.frame_digest,
        "criteria_frame_digest": criteria.frame_digest,
    }


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
    registry = load_registry(store.store_dir)
    if registry is not None:
        entry = next(
            (
                item
                for item in registry.entries
                if item.key == entry_key and item.operation == "SEVER"
            ),
            None,
        )
        if entry is not None and declared_artifact_available(
            store,
            entry=entry,
            evidence=_installation_evidence(source, criteria),
        ):
            return True
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
    if not _semantic_binding_matches(
        prepared.source, source
    ) or not _semantic_binding_matches(prepared.criteria, criteria):
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


def _validate_description(store: MemoryStore, description: dict[str, str]) -> None:
    current = store.load_direct(description["name"])
    if (
        current.uid != description["context_uid"]
        or context_record_digest(current) != description["context_digest"]
    ):
        raise StudyPrewarmRegistryError(
            "Task 3 description changed after Sever was prepared."
        )


def _capture_prepared_basis(
    store: MemoryStore,
    prepared: SeverSession,
    *,
    registry_snapshot: ProfileRegistry | None = None,
) -> tuple[ContextAccess, ContextAccess, SeverContextBinding, SeverContextBinding]:
    """Reload one declared whole request by its exact locators and scope flags."""

    current_name = store.current_context_name()
    source_access = resolve_context_access(
        store,
        prepared.source.root_name,
        current_name=current_name,
        required_permission="READ",
        registry=registry_snapshot,
    )
    criteria_access = resolve_context_access(
        store,
        prepared.criteria.root_name,
        current_name=current_name,
        required_permission="READ",
        registry=registry_snapshot,
    )
    # Import lazily because the production runtime consults this module for an
    # exact lookup after freezing ordinary inputs. The application boundary,
    # rather than the CLI command, owns the shared frame-capture contract.
    from memcommit.operations.sever.runtime import capture_sever_binding

    source = capture_sever_binding(
        source_access,
        include_descendants=prepared.source.include_descendants,
    )
    criteria = capture_sever_binding(
        criteria_access,
        include_descendants=prepared.criteria.include_descendants,
    )
    return source_access, criteria_access, source, criteria


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
        raise StudyPrewarmRegistryError(
            "Sever prewarm requires a participant Study Profile."
        )
    if registry.baseline_profile_uid != identity.baseline_profile_uid:
        raise StudyPrewarmRegistryError(
            "Sever prewarm belongs to a different baseline."
        )
    provider_identity = _configured_semantic_identity()
    declared = skipped = 0
    installed: list[str] = []
    for entry in registry.entries:
        if not entry.enabled or entry.operation != "SEVER":
            continue
        declared += 1
        artifact = load_artifact(store.store_dir, entry)
        prepared, description = _validate_artifact(artifact, entry_key=entry.key)
        cached_identity = (
            artifact.get("provider"),
            artifact.get("model"),
            artifact.get("reasoning"),
        )
        if not prewarm_quality_satisfies(
            cached_identity,  # type: ignore[arg-type]
            provider_identity,
        ):
            skipped += 1
            continue
        _validate_description(store, description)
        source_access, criteria_access, source, criteria = _capture_prepared_basis(
            store,
            prepared,
            registry_snapshot=registry_snapshot,
        )
        output_access = _local_output_access(store, prepared.output_name)
        authorize_combination((source_access, criteria_access))
        authorize_derived_transfer(source_access, output_access)
        authorize_derived_transfer(criteria_access, output_access)
        authorize_analysis_save((source_access, criteria_access), retention="RETAINED")
        _fresh_review(prepared, source=source, criteria=criteria)
        if publish:
            record_declared_installation(
                store,
                entry=entry,
                evidence=_installation_evidence(source, criteria),
            )
            installed.append(entry.key)
    return SeverPrewarmInstallResult(
        declared, len(installed), skipped, tuple(installed)
    )


def _local_output_access(store: MemoryStore, name: str):
    # Kept local to avoid broadening the public Context locator contract for a
    # require-new output name.
    from memcommit.authority.access import ContextAccess

    validate_portable_context_name(name)
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
    matches: list[tuple[SemanticIdentity, SeverSession]] = []
    for entry in registry.entries:
        if not entry.enabled or entry.operation != "SEVER":
            continue
        artifact = load_artifact(store.store_dir, entry)
        prepared, description = _validate_artifact(artifact, entry_key=entry.key)
        cached_identity = (
            artifact.get("provider"),
            artifact.get("model"),
            artifact.get("reasoning"),
        )
        if (
            not prewarm_quality_satisfies(
                cached_identity,  # type: ignore[arg-type]
                provider_identity,
            )
            or prepared.output_name != output_name
        ):
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
        matches.append(
            (
                cached_identity,  # type: ignore[arg-type]
                _fresh_review(prepared, source=source, criteria=criteria),
            )
        )
    selected = highest_quality_candidates(matches)
    if len(selected) > 1:
        raise StudyPrewarmRegistryError(
            "Multiple declared Sever prewarms match the same frozen request."
        )
    return selected[0] if selected else None


def find_installed_projectable_sever_prewarm(
    *,
    store: MemoryStore,
    source: SeverContextBinding,
    criteria: SeverContextBinding,
    output_name: str,
) -> SeverPrewarmMatch | None:
    """Compatibility facade; projection is intentionally unavailable."""

    exact = find_installed_exact_sever_prewarm(
        store=store,
        source=source,
        criteria=criteria,
        output_name=output_name,
    )
    if exact is None:
        return None
    return SeverPrewarmMatch(session=exact, origin="EXACT_PREWARM")


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

    return (
        find_installed_exact_sever_prewarm(
            store=store,
            source=source,
            criteria=criteria,
            output_name=output_name,
        )
        is not None
    )
