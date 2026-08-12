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
from memcommit.comparison import COMPARISON_RULESET_VERSION, ComparisonInput
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
    directional_comparison_basis_assessment,
)
from memcommit.meld_provider import MELD_DIRECTIONAL_PROVIDER_CONTRACT_VERSION
from memcommit.granted_comparison_store import recursive_comparison_projection
from memcommit.profile_config import (
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    study_run_identity,
)
from memcommit.store import MemoryStore, _write_json_atomic, context_record_digest
from memcommit.study_prewarm.installations import (
    INSTALLATIONS_DIRECTORY_NAME,
    declared_installation_matches,
    record_declared_installation,
)
from memcommit.study_prewarm.compare import (
    EquivalentComparePrewarmMatch,
    project_prepared_compare_analysis,
    rebind_equivalent_compare_analysis,
)
from memcommit.study_prewarm.registry import (
    StudyPrewarmRegistryError,
    load_artifact,
    load_registry,
    payload_digest,
)
from memcommit.study_prewarm.scope_equivalence import (
    transparent_context_scope_matches,
    transparent_scope_evidence_matches,
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


@dataclass(frozen=True)
class DirectionalMeldPrewarmMatch:
    """A ready Directional assessment and its visible reuse origin."""

    entry_key: str
    session: MeldSession
    origin: str


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


def _installation_evidence(session: MeldSession) -> dict[str, str]:
    assert session.comparison_seed is not None
    return {
        "incoming_frame_digest": session.frames[0].context_digest,
        "baseline_frame_digest": session.frames[1].context_digest,
        "comparison_seed_digest": session.comparison_seed.analysis_digest,
    }


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
    registry = load_registry(store.store_dir)
    if registry is not None:
        entry = next(
            (
                item
                for item in registry.entries
                if item.key == entry_key
                and item.operation == "MELD_DIRECTIONAL"
            ),
            None,
        )
        if entry is not None and declared_installation_matches(
            store,
            entry=entry,
            evidence=_installation_evidence(session),
        ):
            return True
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


def _meld_frame_evidence(frame: MeldFrame) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            memory.uid,
            memory.position,
            memory.content_digest,
            memory.content,
            memory.owner_context_uid,
            memory.owner_context_name,
        )
        for memory in frame.memories
    )


def _equivalent_semantic_request_matches(
    prepared: MeldSession,
    current: MeldSession,
) -> bool:
    """Match a Directional request whose INCOMING root is an empty wrapper."""

    if (
        prepared.mode != "DIRECTIONAL"
        or current.mode != "DIRECTIONAL"
        or prepared.schema_version
        != current.schema_version
        != MELD_DIRECTIONAL_COMPARISON_SCHEMA_VERSION
        # The baseline frame below proves the complete current target graph.
        # Its aggregate digest may change across regenerated Study Grant
        # bindings, as it already may in the exact portable matcher.
        or prepared.target.context_uid != current.target.context_uid
        or prepared.target.context_name != current.target.context_name
        or _semantic_frame_identity(prepared.frames[1])
        != _semantic_frame_identity(current.frames[1])
        or prepared.comparison_seed is None
        or current.comparison_seed is None
        or not transparent_scope_evidence_matches(
            prepared_root=prepared.frames[0].context_name,
            current_root=current.frames[0].context_name,
            prepared_evidence=_meld_frame_evidence(prepared.frames[0]),
            current_evidence=_meld_frame_evidence(current.frames[0]),
        )
    ):
        return False
    rebound_analysis = rebind_equivalent_compare_analysis(
        prepared.comparison_seed.analysis,
        ComparisonInput(
            uid=current.comparison_seed.analysis.uid,
            created_at=current.comparison_seed.analysis.created_at,
            ruleset_version=current.comparison_seed.analysis.ruleset_version,
            frames=current.comparison_seed.analysis.frames,
            include_descendants=current.comparison_seed.analysis.include_descendants,
        ),
        owner_evidence_proven=(True, False),
    )
    return bool(
        rebound_analysis is not None
        and rebound_analysis.to_dict()
        == current.comparison_seed.analysis.to_dict()
    )


def _rebind_prepared_session(
    prepared: MeldSession,
    *,
    current: MeldSession,
    equivalent_scope: bool = False,
) -> MeldSession:
    """Map session-local frame aliases onto the complete current frame."""

    matches = (
        _equivalent_semantic_request_matches(prepared, current)
        if equivalent_scope
        else _semantic_request_matches(prepared, current)
    )
    if not matches:
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


def _project_prepared_session(
    prepared: MeldSession,
    *,
    current: MeldSession,
) -> MeldSession | None:
    """Project one ready action ledger onto the current Compare subset."""

    if (
        prepared.comparison_seed is None
        or current.comparison_seed is None
        or current.current_turn is None
    ):
        return None
    prepared_assessment = prepared.current_assessment
    if prepared_assessment is None:
        return None
    basis = directional_comparison_basis_assessment(
        current.comparison_seed.analysis,
        (current.frames[0], current.frames[1]),
    )
    frame_uid_map = {
        prior.uid: replacement.uid
        for prior, replacement in zip(prepared.frames, current.frames, strict=True)
    }
    current_keys = {
        (frame.uid, memory.uid)
        for frame in current.frames
        for memory in frame.memories
    }
    current_owner_keys = {
        (context.uid, context.name)
        for context in (current.frames[1].contexts or ())
    }
    parent_relations = {
        relation.uid: {
            (member.frame_uid, member.memory_uid) for member in relation.members
        }
        for relation in prepared_assessment.relations
    }
    projected_relation_by_parent: dict[str, str] = {}
    for relation in basis.relations:
        current_members = {
            (member.frame_uid, member.memory_uid) for member in relation.members
        }
        origins = [
            relation_uid
            for relation_uid, members in parent_relations.items()
            if current_members
            <= {
                (frame_uid_map[frame_uid], memory_uid)
                for frame_uid, memory_uid in members
            }
            and current_members
            & {
                (frame_uid_map[frame_uid], memory_uid)
                for frame_uid, memory_uid in members
            }
        ]
        if len(origins) != 1:
            return None
        projected_relation_by_parent[origins[0]] = relation.uid

    proposals = []
    for proposal in prepared_assessment.proposals:
        source_members = tuple(
            replace(member, frame_uid=frame_uid_map[member.frame_uid])
            for member in proposal.source_members
            if (frame_uid_map[member.frame_uid], member.memory_uid) in current_keys
        )
        relation_uids = tuple(
            projected_relation_by_parent[relation_uid]
            for relation_uid in proposal.relation_uids
            if relation_uid in projected_relation_by_parent
        )
        if not source_members or len(relation_uids) != len(proposal.relation_uids):
            continue
        owner_uid = proposal.owner_context_uid
        owner_name = proposal.owner_context_name
        if (owner_uid, owner_name) not in current_owner_keys:
            if proposal.operation != "ADD" or proposal.disposition != "PRESERVE":
                continue
            # Selecting a narrower BASELINE explicitly changes placement. An
            # exact preservation ADD can therefore be reparented to that
            # selected root without changing its content or semantic decision.
            # EDIT and synthesized results still require their original owner.
            owner_uid = current.frames[1].context_uid
            owner_name = current.frames[1].context_name
        proposals.append(
            replace(
                proposal,
                relation_uids=relation_uids,
                source_members=source_members,
                owner_context_uid=owner_uid,
                owner_context_name=owner_name,
            )
        )
    ready = not any(
        issue.priority == "REQUIRED" for issue in basis.issues
    ) and not any(relation.status == "UNRESOLVED" for relation in basis.relations)
    assessment = MeldAssessment(
        overview=(
            "Projected from the declared Directional Meld basis over the "
            "surviving Compare relation ledger. No provider call was made."
        ),
        relations=basis.relations,
        issues=basis.issues,
        proposals=tuple(proposals),
        ready_to_apply=ready,
    )
    turn = replace(current.current_turn, assessment=assessment)
    try:
        return MeldSession.from_dict(
            replace(
                current,
                state="READY_TO_APPLY" if ready else "AWAITING_REPLY",
                turns=(turn,),
            ).to_dict()
        )
    except MeldError:
        # Coverage, ownership, and relation validation remain authoritative.
        return None


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


def _load_named_complete_context(
    *,
    store: MemoryStore,
    name: str,
    registry_snapshot: ProfileRegistry,
) -> Context:
    access = resolve_context_access(
        store,
        name,
        current_name=store.current_context_name(),
        required_permission="READ",
        registry=registry_snapshot,
    )
    return _load_complete_context(access, registry_snapshot=registry_snapshot)


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
            record_declared_installation(
                store,
                entry=entry,
                evidence=_installation_evidence(current),
            )
            installed.append(entry.key)
    return DirectionalMeldPrewarmInstallResult(
        declared, len(installed), skipped, tuple(installed)
    )


def find_installed_equivalent_directional_comparison(
    *,
    store: MemoryStore,
    comparison_input: ComparisonInput,
    registry_snapshot: ProfileRegistry | None = None,
) -> EquivalentComparePrewarmMatch | None:
    """Reuse the installed Directional artifact's Compare seed after re-rooting."""

    registry = load_registry(store.store_dir)
    if registry is None:
        return None
    profile_registry = registry_snapshot or load_profile_registry()
    configured = _configured_semantic_identity()
    matches: list[EquivalentComparePrewarmMatch] = []
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
            canonical = _current_request(
                store=store,
                registry_snapshot=profile_registry,
                prepared=prepared,
            )
            if not _receipt_matches(store, entry_key=entry.key, session=canonical):
                continue
            assert prepared.comparison_seed is not None
            old_analysis = prepared.comparison_seed.analysis
            owner_evidence = (False, False)
            for index in range(2):
                old_scope = _load_named_complete_context(
                    store=store,
                    name=old_analysis.frames[index].context_name,
                    registry_snapshot=profile_registry,
                )
                new_scope = _load_named_complete_context(
                    store=store,
                    name=comparison_input.frames[index].context_name,
                    registry_snapshot=profile_registry,
                )
                owner_evidence = (
                    *owner_evidence[:index],
                    transparent_context_scope_matches(old_scope, new_scope),
                    *owner_evidence[index + 1 :],
                )
            rebound = rebind_equivalent_compare_analysis(
                old_analysis,
                comparison_input,
                owner_evidence_proven=owner_evidence,
            )
            origin = "EQUIVALENT_SCOPE_PREWARM"
            if rebound is None:
                rebound = project_prepared_compare_analysis(
                    old_analysis,
                    comparison_input,
                    required_orientation=(0, 1),
                )
                origin = "PROJECTED_PREWARM"
        except (OSError, StudyPrewarmRegistryError, ValueError):
            continue
        if rebound is not None:
            matches.append(
                EquivalentComparePrewarmMatch(
                    entry_key=entry.key,
                    analysis=rebound,
                    prepared_context_names=(
                        old_analysis.frames[0].context_name,
                        old_analysis.frames[1].context_name,
                    ),
                    origin=origin,
                )
            )
    return matches[0] if len(matches) == 1 else None


def find_installed_directional_meld_prewarm(
    *,
    store: MemoryStore,
    current: MeldSession,
    registry_snapshot: ProfileRegistry | None = None,
) -> DirectionalMeldPrewarmMatch | None:
    """Return one exact or transparently re-rooted ready proposal."""

    registry = load_registry(store.store_dir)
    if registry is None:
        return None
    profile_registry = registry_snapshot or load_profile_registry()
    configured = _configured_semantic_identity()
    matches: list[DirectionalMeldPrewarmMatch] = []
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
        try:
            canonical = _current_request(
                store=store,
                registry_snapshot=profile_registry,
                prepared=prepared,
            )
        except StudyPrewarmRegistryError:
            # Drift in the installed exact frame invalidates both exact and
            # equivalent reuse. The complete changed request remains live.
            continue
        if not _receipt_matches(store, entry_key=entry.key, session=canonical):
            continue
        exact = _semantic_request_matches(prepared, current)
        equivalent = False
        if not exact:
            try:
                old_scope = _load_named_complete_context(
                    store=store,
                    name=prepared.frames[0].context_name,
                    registry_snapshot=profile_registry,
                )
                new_scope = _load_named_complete_context(
                    store=store,
                    name=current.frames[0].context_name,
                    registry_snapshot=profile_registry,
                )
                equivalent = transparent_context_scope_matches(
                    old_scope,
                    new_scope,
                ) and _equivalent_semantic_request_matches(prepared, current)
            except (OSError, StudyPrewarmRegistryError, ValueError):
                equivalent = False
        projected = None
        if not exact and not equivalent:
            projected = _project_prepared_session(prepared, current=current)
            if projected is None:
                continue
        try:
            matches.append(
                DirectionalMeldPrewarmMatch(
                    entry_key=entry.key,
                    session=(
                        projected
                        if projected is not None
                        else _rebind_prepared_session(
                            prepared,
                            current=current,
                            equivalent_scope=equivalent,
                        )
                    ),
                    origin=(
                        "EXACT_PREWARM"
                        if exact
                        else "EQUIVALENT_SCOPE_PREWARM"
                        if equivalent
                        else "PROJECTED_PREWARM"
                    ),
                )
            )
        except MeldError as error:
            raise StudyPrewarmRegistryError(
                "Directional Meld prewarm could not be rebound."
            ) from error
    if len(matches) > 1:
        raise StudyPrewarmRegistryError(
            "Multiple Directional Meld prewarms match the same frozen request."
        )
    return matches[0] if matches else None


def find_installed_exact_directional_meld_prewarm(
    *, store: MemoryStore, current: MeldSession
) -> MeldSession | None:
    """Compatibility facade retaining the historical exact-only contract."""

    match = find_installed_directional_meld_prewarm(store=store, current=current)
    return (
        match.session
        if match is not None and match.origin == "EXACT_PREWARM"
        else None
    )
