"""Setup-time installation of exact portable Compare analyses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import TYPE_CHECKING
import uuid

from memcommit.operations.compare.ledger.execution import load_comparison_context
from memcommit.authority.access import GrantedReadStore, resolve_context_access
from memcommit.operations.compare.ledger.model import (
    COMPARISON_RULESET_VERSION,
    ComparisonAnalysis,
    ComparisonInput,
    ComparisonIssue,
    ComparisonMember,
    ComparisonRelation,
    ComparisonReports,
    comparison_canonical_digest,
)
from memcommit.operations.compare.ledger.provider import COMPARISON_PROVIDER_CONTRACT_VERSION
from memcommit.infrastructure.config import Config
from memcommit.infrastructure.providers.policy import (
    resolve_operation_provider_policy,
)
from memcommit.context import Context
from memcommit.context_targeting.loading import load_context_scope
from memcommit.authority.derived_policy import (
    analysis_retention,
    authorize_analysis_save,
    authorize_combination,
)
from memcommit.profile_config import ProfileEntry, ProfileRegistry, study_run_identity
from memcommit.store import MemoryStore, _write_json_atomic, context_record_digest
from memcommit.study_prewarm.installations import (
    INSTALLATIONS_DIRECTORY_NAME,
    declared_artifact_available,
    declared_installation_matches,
    record_declared_installation,
)
from memcommit.study_prewarm.registry import (
    StudyPrewarmRegistryError,
    payload_digest,
    load_artifact,
    load_registry,
    uses_shared_bundle,
)
from memcommit.study_prewarm.quality import (
    SemanticIdentity,
    highest_quality_candidates,
    prewarm_quality_satisfies,
)
from memcommit.study_prewarm.scope_equivalence import (
    transparent_context_scope_matches,
    transparent_scope_evidence_matches,
)

if TYPE_CHECKING:
    from memcommit.authority.access import ContextAccess


COMPARE_ARTIFACT_KIND = "STUDY_COMPARE_EXACT_PREWARM"
COMPARE_ARTIFACT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ComparePrewarmInstallResult:
    declared: int
    installed: int
    skipped_configuration: int
    analysis_uids: tuple[str, ...]


@dataclass(frozen=True)
class EquivalentComparePrewarmMatch:
    """One exact semantic ledger rebound to a transparent Context root."""

    entry_key: str
    analysis: ComparisonAnalysis
    prepared_context_names: tuple[str, str]
    origin: str = "EQUIVALENT_SCOPE_PREWARM"


def _same_or_descendant_name(name: str, parent: str) -> bool:
    # The selected locator may sit above or below the prepared root.  The
    # Memory ledger below, rather than depth, decides whether it is reusable.
    return (
        name == parent or name.startswith(parent + "/") or parent.startswith(name + "/")
    )


def _requested_frame_is_parent_subset(requested, parent) -> bool:
    """Match stable Memories while allowing the recursive path prefix.

    A descendant-inclusive parent Compare prefixes flattened content with its
    owning Context name. Loading that exact child without descendants returns
    the original text instead, so both canonical forms must be recognized.
    Durable Memory identity plus one of these exact content forms prevents an
    edited or newly added Memory from entering a projection.
    """

    parent_by_uid = {memory.uid: memory for memory in parent.memories}
    for memory in requested.memories:
        parent_memory = parent_by_uid.get(memory.uid)
        if parent_memory is None:
            return False
        if parent_memory.content not in {
            memory.content,
            f"[{requested.context_name}] {memory.content}",
        }:
            return False
    return True


def _projection_orientation(
    requested: ComparisonInput,
    parent: ComparisonAnalysis,
) -> tuple[int, int] | None:
    """Return the parent side used by each requested side, if unambiguous."""

    matches: list[tuple[int, int]] = []
    for orientation in ((0, 1), (1, 0)):
        if all(
            _same_or_descendant_name(
                requested.frames[index].context_name,
                parent.frames[parent_index].context_name,
            )
            and _requested_frame_is_parent_subset(
                requested.frames[index],
                parent.frames[parent_index],
            )
            for index, parent_index in enumerate(orientation)
        ):
            matches.append(orientation)
    return matches[0] if len(matches) == 1 else None


def _comparison_frame_evidence(frame) -> tuple[tuple[object, ...], ...]:
    """Return every provider-visible Memory field except the frame root."""

    return tuple(
        (
            memory.uid,
            memory.position,
            memory.content_digest,
            memory.content,
        )
        for memory in frame.memories
    )


def _exact_input_matches(
    prepared: ComparisonAnalysis,
    current: ComparisonInput,
) -> bool:
    return bool(
        prepared.include_descendants == current.include_descendants
        and all(
            old.context_uid == new.context_uid
            and old.context_name == new.context_name
            and old.context_digest == new.context_digest
            and _comparison_frame_evidence(old) == _comparison_frame_evidence(new)
            for old, new in zip(prepared.frames, current.frames, strict=True)
        )
    )


def _equivalent_scope_frames(
    prepared: ComparisonAnalysis,
    current: ComparisonInput | ComparisonAnalysis,
    *,
    owner_evidence_proven: tuple[bool, bool] = (False, False),
) -> bool:
    """Match the same ordered two-frame evidence under a lexical re-root."""

    aliased = prepared.include_descendants != current.include_descendants
    for index, (old, new) in enumerate(
        zip(prepared.frames, current.frames, strict=True)
    ):
        old_evidence = _comparison_frame_evidence(old)
        new_evidence = _comparison_frame_evidence(new)
        if (
            old.context_uid == new.context_uid
            and old.context_name == new.context_name
            and old.context_digest == new.context_digest
            and old_evidence == new_evidence
        ):
            continue
        # Recursive Compare projection decorates descendant content with its
        # owner name when the selected root is an ancestor. The live loaded
        # scopes prove raw content and owner equality before that encoding may
        # be ignored; durable Memory identity and order still remain exact.
        projected_evidence_matches = owner_evidence_proven[index] and (
            tuple((row[0], row[1]) for row in old_evidence)
            == tuple((row[0], row[1]) for row in new_evidence)
        )
        if not (
            transparent_scope_evidence_matches(
                prepared_root=old.context_name,
                current_root=new.context_name,
                prepared_evidence=old_evidence,
                current_evidence=new_evidence,
            )
            or (
                projected_evidence_matches
                and transparent_scope_evidence_matches(
                    prepared_root=old.context_name,
                    current_root=new.context_name,
                    prepared_evidence=(),
                    current_evidence=(),
                )
            )
        ):
            return False
        aliased = True
    return aliased


def rebind_equivalent_compare_analysis(
    prepared: ComparisonAnalysis,
    current: ComparisonInput,
    *,
    owner_evidence_proven: tuple[bool, bool] = (False, False),
) -> ComparisonAnalysis | None:
    """Rebind an unchanged exhaustive ledger to current frame identities.

    No relation is filtered or reclassified.  This distinguishes transparent
    scope reuse from the intentionally lossy parent-subset projection below.
    """

    if not _equivalent_scope_frames(
        prepared,
        current,
        owner_evidence_proven=owner_evidence_proven,
    ):
        return None
    frame_uid_map = {
        old.uid: new.uid
        for old, new in zip(prepared.frames, current.frames, strict=True)
    }
    relations: list[ComparisonRelation] = []
    for relation in prepared.relations:
        value = relation.to_dict()
        value["members"] = [
            {
                "frame_uid": frame_uid_map[member.frame_uid],
                "memory_uid": member.memory_uid,
            }
            for member in relation.members
        ]
        relations.append(ComparisonRelation.from_dict(value))
    if prepared.reports is None:
        raise StudyPrewarmRegistryError(
            "Equivalent Compare prewarm is missing current reports."
        )
    return ComparisonAnalysis.create(
        current,
        overview=prepared.overview,
        reports=prepared.reports,
        relations=relations,
        issues=prepared.issues,
    )


def _load_complete_scope(
    *,
    store: MemoryStore,
    name: str,
    current_name: str | None,
    registry_snapshot: ProfileRegistry,
) -> Context:
    access = resolve_context_access(
        store,
        name,
        current_name=current_name,
        required_permission="READ",
        registry=registry_snapshot,
    )
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


def _owner_evidence_matches(
    *,
    store: MemoryStore,
    prepared: ComparisonAnalysis,
    current: ComparisonInput,
    current_name: str | None,
    registry_snapshot: ProfileRegistry,
) -> tuple[bool, bool]:
    matches: list[bool] = []
    for old, new, descendants in zip(
        prepared.frames,
        current.frames,
        current.include_descendants,
        strict=True,
    ):
        if old.context_name == new.context_name:
            matches.append(False)
            continue
        if not descendants:
            matches.append(False)
            continue
        try:
            old_scope = _load_complete_scope(
                store=store,
                name=old.context_name,
                current_name=current_name,
                registry_snapshot=registry_snapshot,
            )
            new_scope = _load_complete_scope(
                store=store,
                name=new.context_name,
                current_name=current_name,
                registry_snapshot=registry_snapshot,
            )
        except (OSError, ValueError):
            matches.append(False)
            continue
        matches.append(transparent_context_scope_matches(old_scope, new_scope))
    return matches[0], matches[1]


def _projection_reports(
    relations: tuple[ComparisonRelation, ...],
    frames,
) -> ComparisonReports:
    reference_uid, compared_uid = (frame.uid for frame in frames)
    both_count = sum(
        relation.kind in {"EQUIVALENT", "COMPATIBLE"} for relation in relations
    )
    differences_count = sum(
        relation.kind in {"SCOPED", "CONFLICT", "UNCLEAR"} for relation in relations
    )
    reference_count = sum(
        relation.kind == "DISTINCT"
        and all(member.frame_uid == reference_uid for member in relation.members)
        for relation in relations
    )
    compared_count = sum(
        relation.kind == "DISTINCT"
        and all(member.frame_uid == compared_uid for member in relation.members)
        for relation in relations
    )

    def report(label: str, count: int) -> str:
        return (
            f"Projected from the declared parent comparison. {count} surviving "
            f"{label} relation group(s) are shown without fresh semantic reanalysis."
            if count
            else ""
        )

    return ComparisonReports(
        both=report("shared", both_count),
        differences=report("difference", differences_count),
        reference_only=report("reference-only", reference_count),
        compared_only=report("compared-only", compared_count),
    )


def _project_analysis(
    parent: ComparisonAnalysis,
    requested: ComparisonInput,
    orientation: tuple[int, int],
) -> ComparisonAnalysis:
    requested_by_parent = {
        parent.frames[parent_index].uid: requested.frames[requested_index]
        for requested_index, parent_index in enumerate(orientation)
    }
    requested_memory_uids = {
        frame.uid: {memory.uid for memory in frame.memories}
        for frame in requested.frames
    }
    relation_uid_map: dict[str, str] = {}
    projected_relations: list[ComparisonRelation] = []
    unresolved_parent_relation_uids: set[str] = set()

    for relation in parent.relations:
        projected_members: list[ComparisonMember] = []
        for member in relation.members:
            requested_frame = requested_by_parent.get(member.frame_uid)
            if (
                requested_frame is None
                or member.memory_uid not in requested_memory_uids[requested_frame.uid]
            ):
                continue
            projected_members.append(
                ComparisonMember(
                    frame_uid=requested_frame.uid,
                    memory_uid=member.memory_uid,
                )
            )
        if not projected_members:
            continue
        surviving_sides = {member.frame_uid for member in projected_members}
        kind = relation.kind
        if kind != "DISTINCT" and len(surviving_sides) != 2:
            # Deleting one side of a cross-source group leaves a valid
            # one-sided primary disposition, but cannot recover another
            # semantic relation that the parent partition may have hidden.
            kind = "DISTINCT"
        status = "UNRESOLVED" if kind in {"CONFLICT", "UNCLEAR"} else "RESOLVED"
        members_key = ",".join(
            f"{member.frame_uid}:{member.memory_uid}" for member in projected_members
        )
        relation_uid = str(
            uuid.uuid5(
                uuid.UUID(requested.uid),
                f"projected-relation:{relation.uid}:{kind}:{members_key}",
            )
        )
        unchanged = kind == relation.kind and len(projected_members) == len(
            relation.members
        )
        projected_relation = ComparisonRelation.from_dict(
            {
                "uid": relation_uid,
                "kind": kind,
                "status": status,
                "members": [member.to_dict() for member in projected_members],
                "summary": (
                    relation.summary
                    if unchanged
                    else "A surviving part of a prewarmed parent relation."
                ),
                "reason": (
                    relation.reason
                    if unchanged
                    else "Unavailable parent members were removed without fresh semantic reanalysis."
                ),
            }
        )
        projected_relations.append(projected_relation)
        relation_uid_map[relation.uid] = relation_uid
        if status == "UNRESOLVED":
            unresolved_parent_relation_uids.add(relation.uid)

    projected_issues: list[ComparisonIssue] = []
    for issue in parent.issues:
        surviving_relation_uids = [
            relation_uid_map[relation_uid]
            for relation_uid in issue.relation_uids
            if relation_uid in unresolved_parent_relation_uids
        ]
        if not surviving_relation_uids:
            continue
        projected_issues.append(
            ComparisonIssue.from_dict(
                {
                    **issue.to_dict(),
                    "uid": str(
                        uuid.uuid5(
                            uuid.UUID(requested.uid),
                            f"projected-issue:{issue.uid}",
                        )
                    ),
                    "relation_uids": surviving_relation_uids,
                }
            )
        )

    relations = tuple(projected_relations)
    return ComparisonAnalysis.create(
        requested,
        overview=(
            "Projection of a declared parent comparison over "
            f"{sum(len(frame.memories) for frame in requested.frames)} "
            "surviving Memories. No fresh semantic reanalysis was performed."
        ),
        reports=_projection_reports(relations, requested.frames),
        relations=relations,
        issues=projected_issues,
    )


def project_prepared_compare_analysis(
    parent: ComparisonAnalysis,
    requested: ComparisonInput,
    *,
    required_orientation: tuple[int, int] | None = None,
) -> ComparisonAnalysis | None:
    """Project a validated basis after an adapter has authorized its origin."""

    orientation = _projection_orientation(requested, parent)
    if orientation is None or (
        required_orientation is not None and orientation != required_orientation
    ):
        return None
    return _project_analysis(parent, requested, orientation)


def _compare_key_material(
    *,
    task: str,
    description: dict[str, object],
    analysis: ComparisonAnalysis,
    provider: object,
    model: object,
    reasoning: object,
    ruleset_version: str = COMPARISON_RULESET_VERSION,
    provider_contract_version: str = COMPARISON_PROVIDER_CONTRACT_VERSION,
) -> dict[str, object]:
    return {
        "operation": "COMPARE",
        "task": task,
        "provider": provider,
        "model": model,
        "reasoning": reasoning,
        "provider_contract_version": provider_contract_version,
        "ruleset_version": ruleset_version,
        "task_description": description,
        "frames": [
            {
                "context_uid": frame.context_uid,
                "context_name": frame.context_name,
                "context_digest": frame.context_digest,
                "include_descendants": include_descendants,
                "memories": [
                    {
                        "uid": memory.uid,
                        "position": memory.position,
                        "content_digest": memory.content_digest,
                    }
                    for memory in frame.memories
                ],
            }
            for frame, include_descendants in zip(
                analysis.frames,
                analysis.include_descendants,
                strict=True,
            )
        ],
    }


def build_compare_prewarm_artifact(
    *,
    task: str,
    task_description: Context,
    analysis: ComparisonAnalysis,
    provider: str,
    model: str,
    reasoning: str | None,
    offline_provider_seconds: float,
) -> tuple[str, dict[str, object]]:
    """Build one portable semantic payload without any Grant wrapper."""

    if task not in {"tutorial", "task-1", "task-2", "task-3"}:
        raise StudyPrewarmRegistryError("Unknown Study task for Compare prewarm.")
    if analysis.ruleset_version != COMPARISON_RULESET_VERSION or any(
        _task_root(frame.context_name) != task for frame in analysis.frames
    ):
        raise StudyPrewarmRegistryError("Compare analysis does not belong to the task.")
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
        raise StudyPrewarmRegistryError("Compare provider evidence is invalid.")
    description = {
        "name": task_description.name,
        "context_uid": task_description.uid,
        "context_digest": context_record_digest(task_description),
    }
    key_material = _compare_key_material(
        task=task,
        description=description,
        analysis=analysis,
        provider=provider,
        model=model,
        reasoning=reasoning,
    )
    key = payload_digest(key_material)
    return key, {
        "kind": COMPARE_ARTIFACT_KIND,
        "schema_version": COMPARE_ARTIFACT_SCHEMA_VERSION,
        "key": key,
        "task": task,
        "operation": "COMPARE",
        "provider": provider,
        "model": model,
        "reasoning": reasoning,
        "provider_contract_version": COMPARISON_PROVIDER_CONTRACT_VERSION,
        "ruleset_version": COMPARISON_RULESET_VERSION,
        "task_description": description,
        "offline_provider_seconds": float(offline_provider_seconds),
        "analysis_digest": comparison_canonical_digest(analysis.to_dict()),
        "analysis": analysis.to_dict(),
    }


def _configured_semantic_identity() -> tuple[str, str | None, str | None]:
    resolved = resolve_operation_provider_policy(
        "compare_contexts",
        config=Config(),
        mode="STUDY_PARTICIPANT",
    )
    return resolved.provider_id, resolved.model, resolved.reasoning_effort


def _task_root(name: str) -> str | None:
    root = name.split("/", 1)[0]
    if root == "practice":
        return "tutorial"
    if root in {"task-1", "task-2", "task-3"}:
        return root
    return None


def _validate_artifact(
    value: dict[str, object],
    *,
    entry_key: str,
    entry_task: str,
    expected_ruleset_version: str = COMPARISON_RULESET_VERSION,
    expected_provider_contract_version: str = COMPARISON_PROVIDER_CONTRACT_VERSION,
) -> tuple[ComparisonAnalysis, dict[str, object]]:
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
        value.get("kind") != COMPARE_ARTIFACT_KIND
        or value.get("schema_version") != COMPARE_ARTIFACT_SCHEMA_VERSION
        or value.get("key") != entry_key
        or value.get("task") != entry_task
        or value.get("operation") != "COMPARE"
        or value.get("provider_contract_version") != expected_provider_contract_version
        or value.get("ruleset_version") != expected_ruleset_version
    ):
        raise StudyPrewarmRegistryError("Declared Compare prewarm is invalid.")
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
        raise StudyPrewarmRegistryError("Compare provider evidence is invalid.")
    raw_analysis = value.get("analysis")
    try:
        analysis = ComparisonAnalysis.from_dict(raw_analysis)
    except Exception as error:
        raise StudyPrewarmRegistryError(
            "Declared Compare analysis is invalid."
        ) from error
    if (
        value.get("analysis_digest") != comparison_canonical_digest(analysis.to_dict())
        or analysis.ruleset_version != expected_ruleset_version
    ):
        raise StudyPrewarmRegistryError("Declared Compare analysis digest is stale.")
    description = value.get("task_description")
    if (
        not isinstance(description, dict)
        or set(description) != {"name", "context_uid", "context_digest"}
        or not all(isinstance(description.get(key), str) for key in description)
    ):
        raise StudyPrewarmRegistryError("Compare task description binding is invalid.")
    if any(_task_root(frame.context_name) != entry_task for frame in analysis.frames):
        raise StudyPrewarmRegistryError("Compare prewarm crosses Study task roots.")
    expected_key = payload_digest(
        _compare_key_material(
            task=entry_task,
            description=description,
            analysis=analysis,
            provider=provider,
            model=model,
            reasoning=reasoning,
            ruleset_version=expected_ruleset_version,
            provider_contract_version=expected_provider_contract_version,
        )
    )
    if expected_key != entry_key:
        raise StudyPrewarmRegistryError("Compare prewarm key is stale.")
    return analysis, description


def find_declared_equivalent_compare_analysis(
    *,
    store: MemoryStore,
    comparison_input: ComparisonInput,
    current_name: str | None,
    registry_snapshot: ProfileRegistry,
) -> EquivalentComparePrewarmMatch | None:
    """Find one installed exact ledger with only a transparent root change."""

    registry = load_registry(store.store_dir)
    if registry is None:
        return None
    if uses_shared_bundle(store.store_dir):
        identity = study_run_identity(registry_snapshot.active)
        if (
            identity is None
            or identity.role != "PARTICIPANT"
            or identity.baseline_profile_uid != registry.baseline_profile_uid
        ):
            return None
    task = _task_root(comparison_input.frames[0].context_name)
    if task is None or _task_root(comparison_input.frames[1].context_name) != task:
        return None
    requested_identity = _configured_semantic_identity()
    candidates: list[tuple[SemanticIdentity, EquivalentComparePrewarmMatch]] = []
    for entry in registry.entries:
        if not entry.enabled or entry.operation != "COMPARE" or entry.task != task:
            continue
        artifact = load_artifact(store.store_dir, entry)
        prepared, description = _validate_artifact(
            artifact,
            entry_key=entry.key,
            entry_task=entry.task,
        )
        cached_identity = (
            artifact.get("provider"),
            artifact.get("model"),
            artifact.get("reasoning"),
        )
        if not prewarm_quality_satisfies(
            cached_identity,  # type: ignore[arg-type]
            requested_identity,
        ) or not _declared_compare_installation_matches(
            store,
            entry=entry,
            analysis=prepared,
            description=description,
        ):
            continue
        description_access = resolve_context_access(
            store,
            str(description["name"]),
            current_name=current_name,
            required_permission="READ",
            registry=registry_snapshot,
        )
        current_description = load_comparison_context(
            description_access,
            registry=registry_snapshot,
        )
        if (
            current_description.uid != description["context_uid"]
            or context_record_digest(current_description)
            != description["context_digest"]
        ):
            continue
        exact = _exact_input_matches(prepared, comparison_input)
        if exact:
            rebound = prepared
        else:
            owner_evidence = _owner_evidence_matches(
                store=store,
                prepared=prepared,
                current=comparison_input,
                current_name=current_name,
                registry_snapshot=registry_snapshot,
            )
            rebound = rebind_equivalent_compare_analysis(
                prepared,
                comparison_input,
                owner_evidence_proven=owner_evidence,
            )
        if rebound is None:
            continue
        candidates.append(
            (
                cached_identity,  # type: ignore[arg-type]
                EquivalentComparePrewarmMatch(
                    entry_key=entry.key,
                    analysis=rebound,
                    prepared_context_names=(
                        prepared.frames[0].context_name,
                        prepared.frames[1].context_name,
                    ),
                    origin=("EXACT_PREWARM" if exact else "EQUIVALENT_SCOPE_PREWARM"),
                ),
            )
        )
    selected = highest_quality_candidates(candidates)
    if len(selected) != 1:
        # An ambiguous semantic origin is not selected by registry order.
        return None
    return selected[0]


def find_declared_projected_compare_analysis(
    *,
    store: MemoryStore,
    comparison_input: ComparisonInput,
    current_name: str | None,
    registry_snapshot: ProfileRegistry,
) -> EquivalentComparePrewarmMatch | None:
    """Project one declared opposite-side parent ledger onto current subsets.

    This is deliberately a Study-only, ephemeral shortcut. It accepts deleted
    members and lexical descendant views, but rejects additions, edits,
    same-parent-side comparisons, cross-task requests, insufficient or
    incomparable cached quality, and ambiguous parent bases. The returned
    analysis is never installed in the durable exact-pair slot.
    """

    registry = load_registry(store.store_dir)
    if registry is None:
        return None
    identity = study_run_identity(registry_snapshot.active)
    if (
        identity is None
        or identity.role != "PARTICIPANT"
        or identity.baseline_profile_uid != registry.baseline_profile_uid
    ):
        return None
    task = _task_root(comparison_input.frames[0].context_name)
    if task is None or _task_root(comparison_input.frames[1].context_name) != task:
        return None
    requested_identity = _configured_semantic_identity()
    candidates: list[
        tuple[
            int,
            SemanticIdentity,
            str,
            ComparisonAnalysis,
            tuple[str, str],
        ]
    ] = []
    for entry in registry.entries:
        if not entry.enabled or entry.operation != "COMPARE" or entry.task != task:
            continue
        artifact = load_artifact(store.store_dir, entry)
        parent, description = _validate_artifact(
            artifact,
            entry_key=entry.key,
            entry_task=entry.task,
        )
        cached_identity = (
            artifact.get("provider"),
            artifact.get("model"),
            artifact.get("reasoning"),
        )
        if not prewarm_quality_satisfies(
            cached_identity,  # type: ignore[arg-type]
            requested_identity,
        ) or not _declared_compare_installation_matches(
            store,
            entry=entry,
            analysis=parent,
            description=description,
        ):
            continue
        description_access = resolve_context_access(
            store,
            str(description["name"]),
            current_name=current_name,
            required_permission="READ",
            registry=registry_snapshot,
        )
        current_description = load_comparison_context(description_access)
        if (
            current_description.uid != description["context_uid"]
            or context_record_digest(current_description)
            != description["context_digest"]
        ):
            # A changed Study description changes the meaning of every
            # operation in that task, so silently projecting the old basis is
            # less safe than surfacing the stale fixture.
            raise StudyPrewarmRegistryError(
                "Study task description changed after Compare was prepared."
            )
        orientation = _projection_orientation(comparison_input, parent)
        if orientation is None:
            continue
        if (
            orientation == (0, 1)
            and parent.include_descendants == comparison_input.include_descendants
            and all(
                requested.context_uid == original.context_uid
                and requested.context_name == original.context_name
                and requested.context_digest == original.context_digest
                for requested, original in zip(
                    comparison_input.frames,
                    parent.frames,
                    strict=True,
                )
            )
        ):
            # The exact installer owns this route. If its durable slot is
            # unexpectedly absent, do not disguise that setup failure as a
            # projection.
            continue
        projected = _project_analysis(parent, comparison_input, orientation)
        parent_size = sum(len(frame.memories) for frame in parent.frames)
        candidates.append(
            (
                parent_size,
                cached_identity,  # type: ignore[arg-type]
                entry.key,
                projected,
                (parent.frames[0].context_name, parent.frames[1].context_name),
            )
        )

    if not candidates:
        return None
    smallest_size = min(candidate[0] for candidate in candidates)
    most_specific = [
        (
            identity,
            (entry_key, analysis, prepared_names),
        )
        for parent_size, identity, entry_key, analysis, prepared_names in candidates
        if parent_size == smallest_size
    ]
    selected = highest_quality_candidates(most_specific)
    if len(selected) != 1:
        # Two equally specific semantic parents make the projection origin
        # ambiguous. Use the ordinary live path instead of selecting one by
        # registry order.
        return None
    entry_key, analysis, prepared_names = selected[0]
    return EquivalentComparePrewarmMatch(
        entry_key=entry_key,
        analysis=analysis,
        prepared_context_names=prepared_names,
        origin="PROJECTED_PREWARM",
    )


def project_declared_compare_analysis(
    *,
    store: MemoryStore,
    comparison_input: ComparisonInput,
    current_name: str | None,
    registry_snapshot: ProfileRegistry,
) -> ComparisonAnalysis | None:
    """Compatibility facade for the ordinary ephemeral Compare path."""

    match = find_declared_projected_compare_analysis(
        store=store,
        comparison_input=comparison_input,
        current_name=current_name,
        registry_snapshot=registry_snapshot,
    )
    return match.analysis if match is not None else None


def _installation_path(store: MemoryStore, analysis_uid: str) -> Path:
    return store.store_dir / INSTALLATIONS_DIRECTORY_NAME / f"{analysis_uid}.json"


def _installation_evidence(
    *,
    analysis: ComparisonAnalysis,
    description: dict[str, str],
) -> dict[str, str]:
    return {
        "analysis_digest": comparison_canonical_digest(analysis.to_dict()),
        "description_context_uid": description["context_uid"],
        "description_context_digest": description["context_digest"],
    }


def _declared_compare_installation_matches(
    store: MemoryStore,
    *,
    entry,
    analysis: ComparisonAnalysis,
    description: dict[str, str],
) -> bool:
    # The legacy materialized receipt remains readable for already-created
    # Study runs; new runs use only the entry-key hidden receipt until first use.
    return declared_artifact_available(
        store,
        entry=entry,
        evidence=_installation_evidence(
            analysis=analysis,
            description=description,
        ),
    ) or is_installed_compare_prewarm(store, analysis)


def _record_installation(
    store: MemoryStore,
    *,
    entry_key: str,
    analysis: ComparisonAnalysis,
) -> None:
    path = _installation_path(store, analysis.uid)
    if path.parent.exists() and (not path.parent.is_dir() or path.parent.is_symlink()):
        raise StudyPrewarmRegistryError("Compare prewarm receipt directory is unsafe.")
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(
        path,
        {
            "kind": "STUDY_COMPARE_PREWARM_INSTALLATION",
            "schema_version": 1,
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "entry_key": entry_key,
            "analysis_uid": analysis.uid,
            "analysis_digest": comparison_canonical_digest(analysis.to_dict()),
        },
    )


def record_exact_compare_prewarm(
    store: MemoryStore,
    *,
    entry_key: str,
    analysis: ComparisonAnalysis,
) -> None:
    """Record the ordinary analysis created by first-use materialization."""

    _record_installation(store, entry_key=entry_key, analysis=analysis)


def record_equivalent_compare_prewarm(
    store: MemoryStore,
    *,
    entry_key: str,
    analysis: ComparisonAnalysis,
    prepared_context_names: tuple[str, str],
) -> None:
    """Record a durable provider-free rebind after Compare saves it."""

    path = _installation_path(store, analysis.uid)
    if path.parent.exists() and (not path.parent.is_dir() or path.parent.is_symlink()):
        raise StudyPrewarmRegistryError("Compare prewarm receipt directory is unsafe.")
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(
        path,
        {
            "kind": "STUDY_COMPARE_EQUIVALENT_SCOPE_PREWARM",
            "schema_version": 1,
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "entry_key": entry_key,
            "analysis_uid": analysis.uid,
            "analysis_digest": comparison_canonical_digest(analysis.to_dict()),
            "prepared_context_names": list(prepared_context_names),
            "current_context_names": [frame.context_name for frame in analysis.frames],
        },
    )


def record_projected_compare_prewarm(
    store: MemoryStore,
    *,
    entry_key: str,
    analysis: ComparisonAnalysis,
    prepared_context_names: tuple[str, str],
) -> None:
    """Record a durable subset ledger used as a Meld prerequisite."""

    path = _installation_path(store, analysis.uid)
    if path.parent.exists() and (not path.parent.is_dir() or path.parent.is_symlink()):
        raise StudyPrewarmRegistryError("Compare prewarm receipt directory is unsafe.")
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(
        path,
        {
            "kind": "STUDY_COMPARE_PROJECTED_PREWARM",
            "schema_version": 1,
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "entry_key": entry_key,
            "analysis_uid": analysis.uid,
            "analysis_digest": comparison_canonical_digest(analysis.to_dict()),
            "prepared_context_names": list(prepared_context_names),
            "current_context_names": [frame.context_name for frame in analysis.frames],
        },
    )


def is_installed_compare_prewarm(
    store: MemoryStore,
    analysis: ComparisonAnalysis,
) -> bool:
    path = _installation_path(store, analysis.uid)
    if path.exists():
        if not path.is_file() or path.is_symlink():
            raise StudyPrewarmRegistryError("Compare prewarm receipt is unsafe.")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise StudyPrewarmRegistryError(
                "Compare prewarm receipt is invalid."
            ) from error
        if (
            isinstance(value, dict)
            and value.get("kind") == "STUDY_COMPARE_PREWARM_INSTALLATION"
            and value.get("schema_version") == 1
            and value.get("analysis_uid") == analysis.uid
            and value.get("analysis_digest")
            == comparison_canonical_digest(analysis.to_dict())
        ):
            return True

    registry = load_registry(store.store_dir)
    if registry is None:
        return False
    for entry in registry.entries:
        if not entry.enabled or entry.operation != "COMPARE":
            continue
        artifact = load_artifact(store.store_dir, entry)
        prepared, description = _validate_artifact(
            artifact,
            entry_key=entry.key,
            entry_task=entry.task,
        )
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


def installed_compare_prewarm_origin(
    store: MemoryStore,
    analysis: ComparisonAnalysis,
) -> str | None:
    """Return the visible exact or transparent prewarm origin, if retained."""

    if is_installed_compare_prewarm(store, analysis):
        return "EXACT_PREWARM"
    path = _installation_path(store, analysis.uid)
    if not path.exists():
        return None
    if not path.is_file() or path.is_symlink():
        raise StudyPrewarmRegistryError("Compare prewarm receipt is unsafe.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise StudyPrewarmRegistryError(
            "Compare prewarm receipt is invalid."
        ) from error
    if not isinstance(value, dict):
        return None
    if (
        value.get("kind") == "STUDY_COMPARE_EQUIVALENT_SCOPE_PREWARM"
        and value.get("schema_version") == 1
        and value.get("analysis_uid") == analysis.uid
        and value.get("analysis_digest")
        == comparison_canonical_digest(analysis.to_dict())
    ):
        return "EQUIVALENT_SCOPE_PREWARM"
    if (
        value.get("kind") == "STUDY_COMPARE_PROJECTED_PREWARM"
        and value.get("schema_version") == 1
        and value.get("analysis_uid") == analysis.uid
        and value.get("analysis_digest")
        == comparison_canonical_digest(analysis.to_dict())
    ):
        return "PROJECTED_PREWARM"
    return None


def install_declared_compare_prewarms(
    *,
    store: MemoryStore,
    profile: ProfileEntry,
    registry_snapshot: ProfileRegistry,
    publish: bool = True,
) -> ComparePrewarmInstallResult:
    """Validate exact Compare seeds and install hidden receipts.

    The portable artifact contains no old Grant wrapper. Every Source is
    resolved and loaded from the new run before the production Compare CAS
    boundary revalidates it and writes a run-local wrapper.
    """

    registry = load_registry(store.store_dir)
    if registry is None:
        return ComparePrewarmInstallResult(0, 0, 0, ())
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
    current_name = store.current_context_name()
    installed = 0
    declared = 0
    skipped = 0
    for entry in registry.entries:
        if not entry.enabled or entry.operation != "COMPARE":
            continue
        declared += 1
        artifact = load_artifact(store.store_dir, entry)
        analysis, description = _validate_artifact(
            artifact,
            entry_key=entry.key,
            entry_task=entry.task,
        )
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
        accesses: list[ContextAccess] = []
        contexts = []
        for frame, include_descendants in zip(
            analysis.frames,
            analysis.include_descendants,
            strict=True,
        ):
            access = resolve_context_access(
                store,
                frame.context_name,
                current_name=current_name,
                required_permission="READ",
                registry=registry_snapshot,
            )
            accesses.append(access)
            contexts.append(
                load_comparison_context(
                    access,
                    include_descendants=include_descendants,
                    registry=registry_snapshot,
                )
            )
        description_access = resolve_context_access(
            store,
            str(description["name"]),
            current_name=current_name,
            required_permission="READ",
            registry=registry_snapshot,
        )
        description_context = load_comparison_context(description_access)
        if (
            description_context.uid != description["context_uid"]
            or context_record_digest(description_context)
            != description["context_digest"]
        ):
            raise StudyPrewarmRegistryError(
                "Study task description changed after Compare was prepared."
            )
        if not analysis.matches(contexts[0], contexts[1]):
            raise StudyPrewarmRegistryError(
                "Declared Compare prewarm does not match the current Sources."
            )
        authorize_combination(accesses)
        retention = (
            analysis_retention(accesses)
            if any(access.is_granted for access in accesses)
            else None
        )
        if any(access.is_granted for access in accesses) and retention is None:
            raise StudyPrewarmRegistryError(
                "Declared Compare prewarm cannot be retained under current Grants."
            )
        if retention is not None:
            authorize_analysis_save(accesses, retention=retention)
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
    return ComparePrewarmInstallResult(
        declared=declared,
        installed=installed,
        skipped_configuration=skipped,
        analysis_uids=(),
    )
