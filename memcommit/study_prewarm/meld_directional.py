"""Declared exact Task 1 Directional Meld reuse.

The artifact is installed as a hidden receipt. It does not create a Meld row
until the participant starts the exact declared operation. At that boundary
the complete current frames and Compare seed are checked before the prepared
assessment is rebound to this run's regenerated Grant identities.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path

from memcommit.commands.granted_context import (
    GrantedReadStore,
    freeze_granted_context_binding,
    resolve_context_access,
)
from memcommit.comparison import COMPARISON_RULESET_VERSION
from memcommit.config import Config
from memcommit.context import Context
from memcommit.context_targeting.loading import load_context_scope
from memcommit.derived_policy import (
    analysis_retention,
    authorize_analysis_save,
    authorize_combination,
    authorize_derived_transfer,
)
from memcommit.meld import (
    MELD_DIRECTIONAL_COMPARISON_SCHEMA_VERSION,
    MeldError,
    MeldFrame,
    MeldAssessment,
    MeldSession,
)
from memcommit.meld_provider import MELD_DIRECTIONAL_PROVIDER_CONTRACT_VERSION
from memcommit.granted_comparison_store import recursive_comparison_projection
from memcommit.profile_config import ProfileEntry, ProfileRegistry, study_run_identity
from memcommit.store import MemoryStore, _write_json_atomic, context_record_digest
from memcommit.study_prewarm.compare import INSTALLATIONS_DIRECTORY_NAME
from memcommit.study_prewarm.registry import (
    StudyPrewarmRegistryError,
    load_artifact,
    load_registry,
    payload_digest,
)


MELD_DIRECTIONAL_ARTIFACT_KIND = "STUDY_MELD_DIRECTIONAL_EXACT_PREWARM"
MELD_DIRECTIONAL_ARTIFACT_SCHEMA_VERSION = 1
TASK = "task-1"
DESCRIPTION_NAME = "task-1/description"
INCOMING_NAME = "task-1/participant/construction-updates"
BASELINE_NAME = "task-1/campus-wiki"


@dataclass(frozen=True)
class DirectionalMeldPrewarmInstallResult:
    declared: int
    installed: int
    skipped_configuration: int
    entry_keys: tuple[str, ...]


def _portable_session(session: MeldSession) -> MeldSession:
    """Retain semantic decisions while removing run-local/application state."""

    try:
        return MeldSession.from_dict(
            replace(
                session,
                state="READY_TO_APPLY",
                granted_incoming=None,
                granted_target=None,
                application=None,
            ).to_dict()
        )
    except MeldError as error:
        raise StudyPrewarmRegistryError(
            "Task 1 Directional Meld prewarm session is invalid."
        ) from error


def _description_identity(description: Context) -> dict[str, str]:
    return {
        "name": description.name,
        "context_uid": description.uid,
        "context_digest": context_record_digest(description),
    }


def _frame_identity(frame: MeldFrame) -> dict[str, object]:
    value = frame.to_dict()
    # Frame UIDs are session-local aliases. The complete Context ledger,
    # Memory ledger, scope, role, and ownership remain exact semantic input.
    value.pop("uid")
    return value


def _semantic_frame_identity(frame: MeldFrame) -> dict[str, object]:
    """Return the portable evidence ledger without run-local graph metadata."""

    value = _frame_identity(frame)
    value.pop("context_digest")
    contexts = value.get("contexts")
    if isinstance(contexts, list):
        # Generated Study Grants can change non-Memory Context-record digests
        # across runs. Context/Memory durable identities, order, ownership, and
        # content are the portable semantic evidence; current graph digests are
        # rebound and checked again by Meld's ordinary save/apply boundary.
        value["contexts"] = [
            {"uid": item["uid"], "name": item["name"]}
            for item in contexts
            if isinstance(item, dict)
        ]
    return value


def _key_material(
    *,
    description: dict[str, str],
    session: MeldSession,
    provider: str,
    model: str,
    reasoning: str | None,
) -> dict[str, object]:
    assert session.comparison_seed is not None
    return {
        "operation": "MELD_DIRECTIONAL",
        "task": TASK,
        "provider": provider,
        "model": model,
        "reasoning": reasoning,
        "provider_contract_version": MELD_DIRECTIONAL_PROVIDER_CONTRACT_VERSION,
        "meld_schema_version": MELD_DIRECTIONAL_COMPARISON_SCHEMA_VERSION,
        "comparison_ruleset_version": COMPARISON_RULESET_VERSION,
        "task_description": description,
        "incoming": _frame_identity(session.frames[0]),
        "baseline": _frame_identity(session.frames[1]),
        "target": session.target.to_dict(),
        "comparison_seed_digest": session.comparison_seed.analysis_digest,
        "assessment_digest": payload_digest(
            session.current_assessment.to_dict()  # type: ignore[union-attr]
        ),
    }


def build_directional_meld_prewarm_artifact(
    *,
    task_description: Context,
    session: MeldSession,
    provider: str,
    model: str,
    reasoning: str | None,
    offline_provider_seconds: float,
) -> tuple[str, dict[str, object]]:
    """Build one portable exact Task 1 Directional Meld artifact."""

    portable = _portable_session(session)
    assessment = portable.current_assessment
    if (
        task_description.name != DESCRIPTION_NAME
        or portable.mode != "DIRECTIONAL"
        or portable.schema_version != MELD_DIRECTIONAL_COMPARISON_SCHEMA_VERSION
        or portable.frames[0].context_name != INCOMING_NAME
        or portable.frames[1].context_name != BASELINE_NAME
        or portable.frames[0].include_descendants is not True
        or portable.frames[1].include_descendants is not True
        or portable.comparison_seed is None
        or assessment is None
        or not assessment.ready_to_apply
        or not portable.turns
        or len(portable.turns) != 1
        or not isinstance(offline_provider_seconds, (int, float))
        or isinstance(offline_provider_seconds, bool)
        or offline_provider_seconds < 0
    ):
        raise StudyPrewarmRegistryError(
            "Task 1 Directional Meld prewarm basis is invalid."
        )
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
        "kind": MELD_DIRECTIONAL_ARTIFACT_KIND,
        "schema_version": MELD_DIRECTIONAL_ARTIFACT_SCHEMA_VERSION,
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
) -> tuple[MeldSession, dict[str, str]]:
    if (
        value.get("kind") != MELD_DIRECTIONAL_ARTIFACT_KIND
        or value.get("schema_version") != MELD_DIRECTIONAL_ARTIFACT_SCHEMA_VERSION
        or value.get("key") != entry_key
        or value.get("operation") != "MELD_DIRECTIONAL"
        or value.get("task") != TASK
        or value.get("provider_contract_version")
        != MELD_DIRECTIONAL_PROVIDER_CONTRACT_VERSION
        or value.get("meld_schema_version")
        != MELD_DIRECTIONAL_COMPARISON_SCHEMA_VERSION
        or value.get("comparison_ruleset_version") != COMPARISON_RULESET_VERSION
    ):
        raise StudyPrewarmRegistryError("Declared Directional Meld prewarm is invalid.")
    description = value.get("task_description")
    if (
        not isinstance(description, dict)
        or set(description) != {"name", "context_uid", "context_digest"}
        or not all(isinstance(item, str) for item in description.values())
    ):
        raise StudyPrewarmRegistryError("Meld task description identity is invalid.")
    try:
        session = MeldSession.from_dict(value.get("session"))
    except (TypeError, ValueError, MeldError) as error:
        raise StudyPrewarmRegistryError(
            "Declared Directional Meld session is invalid."
        ) from error
    assessment = session.current_assessment
    if (
        session != _portable_session(session)
        or session.mode != "DIRECTIONAL"
        or session.schema_version != MELD_DIRECTIONAL_COMPARISON_SCHEMA_VERSION
        or session.frames[0].context_name != INCOMING_NAME
        or session.frames[1].context_name != BASELINE_NAME
        or session.frames[0].include_descendants is not True
        or session.frames[1].include_descendants is not True
        or session.comparison_seed is None
        or assessment is None
        or not assessment.ready_to_apply
        or len(session.turns) != 1
        or value.get("session_digest") != payload_digest(session.to_dict())
        or value.get("assessment_digest") != payload_digest(assessment.to_dict())
    ):
        raise StudyPrewarmRegistryError("Declared Directional Meld session is stale.")
    provider = value.get("provider")
    model = value.get("model")
    reasoning = value.get("reasoning")
    if (
        not isinstance(provider, str)
        or not isinstance(model, str)
        or (reasoning is not None and not isinstance(reasoning, str))
    ):
        raise StudyPrewarmRegistryError("Meld provider identity is invalid.")
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
        raise StudyPrewarmRegistryError("Directional Meld prewarm key is stale.")
    return session, description  # type: ignore[return-value]


def _receipt_path(store: MemoryStore, entry_key: str) -> Path:
    return (
        store.store_dir
        / INSTALLATIONS_DIRECTORY_NAME
        / f"meld-directional-{entry_key}.json"
    )


def _record_installation(
    store: MemoryStore, *, entry_key: str, session: MeldSession
) -> None:
    assert session.comparison_seed is not None
    path = _receipt_path(store, entry_key)
    if path.parent.exists() and (not path.parent.is_dir() or path.parent.is_symlink()):
        raise StudyPrewarmRegistryError(
            "Directional Meld prewarm receipt directory is unsafe."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(
        path,
        {
            "kind": "STUDY_MELD_DIRECTIONAL_PREWARM_INSTALLATION",
            "schema_version": 1,
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "entry_key": entry_key,
            "incoming_frame_digest": session.frames[0].context_digest,
            "baseline_frame_digest": session.frames[1].context_digest,
            "comparison_seed_digest": session.comparison_seed.analysis_digest,
        },
    )


def _receipt_matches(
    store: MemoryStore, *, entry_key: str, session: MeldSession
) -> bool:
    path = _receipt_path(store, entry_key)
    if not path.exists():
        return False
    if not path.is_file() or path.is_symlink():
        raise StudyPrewarmRegistryError("Directional Meld prewarm receipt is unsafe.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise StudyPrewarmRegistryError(
            "Directional Meld prewarm receipt is invalid."
        ) from error
    return bool(
        isinstance(value, dict)
        and value.get("kind") == "STUDY_MELD_DIRECTIONAL_PREWARM_INSTALLATION"
        and value.get("schema_version") == 1
        and value.get("entry_key") == entry_key
        and value.get("incoming_frame_digest") == session.frames[0].context_digest
        and value.get("baseline_frame_digest") == session.frames[1].context_digest
        and session.comparison_seed is not None
        and value.get("comparison_seed_digest")
        == session.comparison_seed.analysis_digest
    )


def _validate_description(store: MemoryStore, description: dict[str, str]) -> None:
    current = store.load_direct(description["name"])
    if (
        current.uid != description["context_uid"]
        or context_record_digest(current) != description["context_digest"]
    ):
        raise StudyPrewarmRegistryError(
            "Task 1 description changed after Directional Meld was prepared."
        )


def _semantic_request_matches(prepared: MeldSession, current: MeldSession) -> bool:
    return bool(
        prepared.mode == current.mode == "DIRECTIONAL"
        and prepared.schema_version
        == current.schema_version
        == MELD_DIRECTIONAL_COMPARISON_SCHEMA_VERSION
        and tuple(_semantic_frame_identity(frame) for frame in prepared.frames)
        == tuple(_semantic_frame_identity(frame) for frame in current.frames)
        and prepared.target.context_uid == current.target.context_uid
        and prepared.target.context_name == current.target.context_name
        and prepared.comparison_seed is not None
        and current.comparison_seed is not None
        and prepared.comparison_seed.to_dict() == current.comparison_seed.to_dict()
    )


def _rebind_prepared_session(
    prepared: MeldSession, *, current: MeldSession
) -> MeldSession:
    """Map session-local frame aliases onto the complete current frame."""

    if not _semantic_request_matches(prepared, current):
        raise StudyPrewarmRegistryError(
            "Declared Directional Meld prewarm does not match current inputs."
        )
    frame_uid_map = {
        prior.uid: replacement.uid
        for prior, replacement in zip(prepared.frames, current.frames, strict=True)
    }
    assessment = prepared.current_assessment
    assert assessment is not None
    value = assessment.to_dict()
    for relation in value["relations"]:  # type: ignore[index]
        for member in relation["members"]:  # type: ignore[index]
            member["frame_uid"] = frame_uid_map[member["frame_uid"]]
    for proposal in value["proposals"]:  # type: ignore[index]
        for member in proposal["source_members"]:  # type: ignore[index]
            member["frame_uid"] = frame_uid_map[member["frame_uid"]]
    rebound_assessment = MeldAssessment.from_dict(value)
    rebound_turn = replace(prepared.turns[0], assessment=rebound_assessment)
    try:
        return MeldSession.from_dict(
            replace(
                prepared,
                frames=current.frames,
                target=current.target,
                comparison_seed=current.comparison_seed,
                granted_incoming=current.granted_incoming,
                granted_target=current.granted_target,
                turns=(rebound_turn,),
            ).to_dict()
        )
    except MeldError as error:
        raise StudyPrewarmRegistryError(
            "Directional Meld prewarm could not be rebound."
        ) from error


def _load_complete_context(access, *, registry_snapshot: ProfileRegistry) -> Context:
    reader = (
        GrantedReadStore(access, registry=registry_snapshot)
        if access.is_granted
        else access.store
    )
    return load_context_scope(
        reader,
        access.display_name if access.is_granted else access.context_name,
        include_descendants=True,
    )


def _current_request(
    *,
    store: MemoryStore,
    registry_snapshot: ProfileRegistry,
    prepared: MeldSession,
) -> MeldSession:
    current_name = store.current_context_name()
    incoming_access = resolve_context_access(
        store,
        INCOMING_NAME,
        current_name=current_name,
        required_permission="READ",
        registry=registry_snapshot,
    )
    baseline_access = resolve_context_access(
        store,
        BASELINE_NAME,
        current_name=current_name,
        required_permission="READ",
        registry=registry_snapshot,
    )
    authorize_combination((incoming_access, baseline_access))
    authorize_derived_transfer(incoming_access, baseline_access)
    retention = analysis_retention((incoming_access, baseline_access))
    if retention is None:
        raise StudyPrewarmRegistryError(
            "Directional Meld prewarm cannot retain analysis under current Grants."
        )
    authorize_analysis_save((incoming_access, baseline_access), retention=retention)
    incoming = _load_complete_context(
        incoming_access, registry_snapshot=registry_snapshot
    )
    baseline = _load_complete_context(
        baseline_access, registry_snapshot=registry_snapshot
    )
    assert prepared.comparison_seed is not None
    analysis = prepared.comparison_seed.analysis
    if (
        analysis.ruleset_version != COMPARISON_RULESET_VERSION
        or analysis.include_descendants != (True, True)
        or not analysis.matches(
            recursive_comparison_projection(incoming),
            recursive_comparison_projection(baseline),
        )
    ):
        raise StudyPrewarmRegistryError(
            "Directional Meld prewarm Compare basis does not match current inputs."
        )
    return MeldSession.create_directional_from_comparison(
        analysis,
        incoming,
        baseline,
        granted_incoming=(
            freeze_granted_context_binding(incoming_access)
            if incoming_access.is_granted
            else None
        ),
        granted_target=(
            freeze_granted_context_binding(baseline_access)
            if baseline_access.is_granted
            else None
        ),
    )


def install_declared_directional_meld_prewarms(
    *,
    store: MemoryStore,
    profile: ProfileEntry,
    registry_snapshot: ProfileRegistry,
    publish: bool = True,
) -> DirectionalMeldPrewarmInstallResult:
    """Validate exact inputs and install only a hidden lookup receipt."""

    registry = load_registry(store.store_dir)
    if registry is None:
        return DirectionalMeldPrewarmInstallResult(0, 0, 0, ())
    identity = study_run_identity(profile)
    if identity is None or identity.role != "PARTICIPANT":
        raise StudyPrewarmRegistryError(
            "Directional Meld prewarm requires a participant Study Profile."
        )
    if registry.baseline_profile_uid != identity.baseline_profile_uid:
        raise StudyPrewarmRegistryError(
            "Directional Meld prewarm belongs to a different baseline."
        )
    configured = _configured_semantic_identity()
    declared = skipped = 0
    installed: list[str] = []
    for entry in registry.entries:
        if not entry.enabled or entry.operation != "MELD_DIRECTIONAL":
            continue
        declared += 1
        artifact = load_artifact(store.store_dir, entry)
        prepared, description = _validate_artifact(artifact, entry_key=entry.key)
        if (
            artifact.get("provider"),
            artifact.get("model"),
            artifact.get("reasoning"),
        ) != configured:
            skipped += 1
            continue
        _validate_description(store, description)
        current = _current_request(
            store=store,
            registry_snapshot=registry_snapshot,
            prepared=prepared,
        )
        _rebind_prepared_session(prepared, current=current)
        if publish:
            _record_installation(store, entry_key=entry.key, session=current)
            installed.append(entry.key)
    return DirectionalMeldPrewarmInstallResult(
        declared, len(installed), skipped, tuple(installed)
    )


def find_installed_exact_directional_meld_prewarm(
    *, store: MemoryStore, current: MeldSession
) -> MeldSession | None:
    """Return the exact ready proposal, or ``None`` so Meld runs live."""

    registry = load_registry(store.store_dir)
    if registry is None:
        return None
    configured = _configured_semantic_identity()
    matches: list[MeldSession] = []
    for entry in registry.entries:
        if not entry.enabled or entry.operation != "MELD_DIRECTIONAL":
            continue
        artifact = load_artifact(store.store_dir, entry)
        prepared, description = _validate_artifact(artifact, entry_key=entry.key)
        if (
            artifact.get("provider"),
            artifact.get("model"),
            artifact.get("reasoning"),
        ) != configured:
            continue
        try:
            _validate_description(store, description)
        except StudyPrewarmRegistryError:
            # A post-setup task edit is an ordinary exact miss; live Meld
            # remains available for the complete changed frame.
            continue
        if not _receipt_matches(store, entry_key=entry.key, session=current):
            continue
        if not _semantic_request_matches(prepared, current):
            continue
        try:
            matches.append(_rebind_prepared_session(prepared, current=current))
        except MeldError as error:
            raise StudyPrewarmRegistryError(
                "Directional Meld prewarm could not be rebound."
            ) from error
    if len(matches) > 1:
        raise StudyPrewarmRegistryError(
            "Multiple Directional Meld prewarms match the same frozen request."
        )
    return matches[0] if matches else None
