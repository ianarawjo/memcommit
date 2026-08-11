"""Setup-time installation of exact portable Compare analyses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import TYPE_CHECKING
import uuid

from memcommit.commands.comparison_execution import (
    install_prepared_comparison_analysis,
    load_comparison_context,
)
from memcommit.commands.granted_context import resolve_context_access
from memcommit.comparison import (
    COMPARISON_RULESET_VERSION,
    ComparisonAnalysis,
    ComparisonInput,
    ComparisonIssue,
    ComparisonMember,
    ComparisonRelation,
    ComparisonReports,
    comparison_canonical_digest,
)
from memcommit.comparison_provider import COMPARISON_PROVIDER_CONTRACT_VERSION
from memcommit.config import Config
from memcommit.context import Context
from memcommit.derived_policy import (
    analysis_retention,
    authorize_analysis_save,
    authorize_combination,
)
from memcommit.profile_config import ProfileEntry, ProfileRegistry, study_run_identity
from memcommit.store import MemoryStore, _write_json_atomic, context_record_digest
from memcommit.study_prewarm.registry import (
    StudyPrewarmRegistryError,
    payload_digest,
    load_artifact,
    load_registry,
)

if TYPE_CHECKING:
    from memcommit.commands.granted_context import ContextAccess


COMPARE_ARTIFACT_KIND = "STUDY_COMPARE_EXACT_PREWARM"
COMPARE_ARTIFACT_SCHEMA_VERSION = 1
INSTALLATIONS_DIRECTORY_NAME = "study-prewarm-installations"


@dataclass(frozen=True)
class ComparePrewarmInstallResult:
    declared: int
    installed: int
    skipped_configuration: int
    analysis_uids: tuple[str, ...]


def _same_or_descendant_name(name: str, parent: str) -> bool:
    return name == parent or name.startswith(parent + "/")


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


def _projection_reports(
    relations: tuple[ComparisonRelation, ...],
    frames,
) -> ComparisonReports:
    reference_uid, compared_uid = (frame.uid for frame in frames)
    both_count = sum(
        relation.kind in {"EQUIVALENT", "COMPATIBLE"}
        for relation in relations
    )
    differences_count = sum(
        relation.kind in {"SCOPED", "CONFLICT", "UNCLEAR"}
        for relation in relations
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
                or member.memory_uid
                not in requested_memory_uids[requested_frame.uid]
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
        status = (
            "UNRESOLVED" if kind in {"CONFLICT", "UNCLEAR"} else "RESOLVED"
        )
        members_key = ",".join(
            f"{member.frame_uid}:{member.memory_uid}"
            for member in projected_members
        )
        relation_uid = str(
            uuid.uuid5(
                uuid.UUID(requested.uid),
                f"projected-relation:{relation.uid}:{kind}:{members_key}",
            )
        )
        unchanged = (
            kind == relation.kind
            and len(projected_members) == len(relation.members)
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


def _compare_key_material(
    *,
    task: str,
    description: dict[str, object],
    analysis: ComparisonAnalysis,
    provider: object,
    model: object,
    reasoning: object,
) -> dict[str, object]:
    return {
        "operation": "COMPARE",
        "task": task,
        "provider": provider,
        "model": model,
        "reasoning": reasoning,
        "provider_contract_version": COMPARISON_PROVIDER_CONTRACT_VERSION,
        "ruleset_version": COMPARISON_RULESET_VERSION,
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
    if (
        analysis.ruleset_version != COMPARISON_RULESET_VERSION
        or any(_task_root(frame.context_name) != task for frame in analysis.frames)
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
    config = Config()
    provider = config.semantic_provider()
    model = config.model_for_provider(provider)
    reasoning = (
        config.codex_reasoning_effort()
        if provider == "codex_chatgpt"
        else None
    )
    return provider, model, reasoning


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
        or value.get("provider_contract_version")
        != COMPARISON_PROVIDER_CONTRACT_VERSION
        or value.get("ruleset_version") != COMPARISON_RULESET_VERSION
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
        value.get("analysis_digest")
        != comparison_canonical_digest(analysis.to_dict())
        or analysis.ruleset_version != COMPARISON_RULESET_VERSION
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
        )
    )
    if expected_key != entry_key:
        raise StudyPrewarmRegistryError("Compare prewarm key is stale.")
    return analysis, description


def project_declared_compare_analysis(
    *,
    store: MemoryStore,
    comparison_input: ComparisonInput,
    current_name: str | None,
    registry_snapshot: ProfileRegistry,
) -> ComparisonAnalysis | None:
    """Project one declared opposite-side parent ledger onto current subsets.

    This is deliberately a Study-only, ephemeral shortcut. It accepts deleted
    members and lexical descendant views, but rejects additions, edits,
    same-parent-side comparisons, cross-task requests, configuration drift,
    and ambiguous parent bases. The returned analysis is never installed in
    the durable exact-pair slot.
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
    if (
        task is None
        or _task_root(comparison_input.frames[1].context_name) != task
    ):
        return None
    provider, model, reasoning = _configured_semantic_identity()
    candidates: list[tuple[int, str, ComparisonAnalysis]] = []
    for entry in registry.entries:
        if (
            not entry.enabled
            or entry.operation != "COMPARE"
            or entry.task != task
        ):
            continue
        artifact = load_artifact(store.store_dir, entry)
        parent, description = _validate_artifact(
            artifact,
            entry_key=entry.key,
            entry_task=entry.task,
        )
        if (
            artifact.get("provider") != provider
            or artifact.get("model") != model
            or artifact.get("reasoning") != reasoning
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
            and parent.include_descendants
            == comparison_input.include_descendants
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
        candidates.append((parent_size, entry.key, projected))

    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        # Two equally specific semantic parents make the projection origin
        # ambiguous. Use the ordinary live path instead of selecting one by
        # registry order.
        return None
    return candidates[0][2]


def _installation_path(store: MemoryStore, analysis_uid: str) -> Path:
    return store.store_dir / INSTALLATIONS_DIRECTORY_NAME / f"{analysis_uid}.json"


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


def is_installed_compare_prewarm(
    store: MemoryStore,
    analysis: ComparisonAnalysis,
) -> bool:
    path = _installation_path(store, analysis.uid)
    if not path.exists():
        return False
    if not path.is_file() or path.is_symlink():
        raise StudyPrewarmRegistryError("Compare prewarm receipt is unsafe.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise StudyPrewarmRegistryError("Compare prewarm receipt is invalid.") from error
    return bool(
        isinstance(value, dict)
        and value.get("kind") == "STUDY_COMPARE_PREWARM_INSTALLATION"
        and value.get("schema_version") == 1
        and value.get("analysis_uid") == analysis.uid
        and value.get("analysis_digest")
        == comparison_canonical_digest(analysis.to_dict())
    )


def install_declared_compare_prewarms(
    *,
    store: MemoryStore,
    profile: ProfileEntry,
    registry_snapshot: ProfileRegistry,
    publish: bool = True,
) -> ComparePrewarmInstallResult:
    """Install exact Compare seeds using this run's current Grant bindings.

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
    provider, model, reasoning = _configured_semantic_identity()
    current_name = store.current_context_name()
    installed: list[str] = []
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
        if (
            artifact.get("provider") != provider
            or artifact.get("model") != model
            or artifact.get("reasoning") != reasoning
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
        retention = analysis_retention(accesses) if any(
            access.is_granted for access in accesses
        ) else None
        if any(access.is_granted for access in accesses) and retention is None:
            raise StudyPrewarmRegistryError(
                "Declared Compare prewarm cannot be retained under current Grants."
            )
        if retention is not None:
            authorize_analysis_save(accesses, retention=retention)
        if publish:
            execution = install_prepared_comparison_analysis(
                store=store,
                reference_access=accesses[0],
                compared_access=accesses[1],
                reference=contexts[0],
                compared=contexts[1],
                current_name=current_name,
                include_descendants=analysis.include_descendants,
                analysis=analysis,
            )
            _record_installation(
                store,
                entry_key=entry.key,
                analysis=execution.analysis,
            )
            installed.append(execution.analysis.uid)
    return ComparePrewarmInstallResult(
        declared=declared,
        installed=len(installed),
        skipped_configuration=skipped,
        analysis_uids=tuple(installed),
    )
