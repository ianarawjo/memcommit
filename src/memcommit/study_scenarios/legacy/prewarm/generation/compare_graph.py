"""Prewarm a hidden task-local Compare graph for one fixed legacy Study run.

The graph is deliberately separate from participant-facing ComparisonAnalysis
and session stores.  Every readable Context below one Study task prefix becomes
one descendant-inclusive view, and every unordered pair inside that task is
evaluated exactly once.  Cross-task pairs are never created.  The task
description digest conditions every pair key, while the description Context
also remains an ordinary graph view so the fixed study frame is explicit.

Pair files contain compact decisions and source identities, not repeated
Memory prose or a rendered report.  They are resumable setup artifacts.  A
later foreground adapter can validate the task, description, view, model, and
ruleset digests before projecting one selected pair into a normal report.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import itertools
import json
import os
from pathlib import Path
import sys
import threading
import time
from typing import Protocol
import uuid

from memcommit.application.operations.compare.ledger.execution import (
    load_comparison_context,
    recursive_comparison_projection,
)
from memcommit.application.capabilities.authority.context_access import resolve_context_access
from memcommit.core.context_targeting.readable_catalog import (
    ReadableContextCatalog,
    freeze_profile_readable_context_catalog,
)
from memcommit.application.operations.compare.ledger.model import (
    COMPARISON_RULESET_VERSION,
    ComparisonAnalysis,
    ComparisonInput,
    ComparisonMember,
    context_record_digest,
)
from memcommit.configuration.config import Config
from memcommit.core.context import Context, Memory
from memcommit.providers.policy import (
    resolve_codex_evaluation_policy,
)
from memcommit.study_scenarios.legacy.prewarm.compare_compact import (
    COMPACT_PROMPT_VERSION,
    run_compact_compare,
)
from memcommit.application.operations.compare.ledger.provider import analyze_comparison
from memcommit.application.operations.profile.config import load_profile_registry
from memcommit.application.operations.profile.model import _study_practice_contexts
from memcommit.providers.types import (
    CODEX_CHATGPT_PROVIDER,
    CODEX_REASONING_EFFORTS,
    ProviderIdentity,
)
from memcommit.providers.subscription import CodexChatGPTProvider
from memcommit.persistence.store import MemoryStore


KIND = "STUDY_COMPARE_GRAPH_PREWARM"
SCHEMA_VERSION = 1
PAIR_KIND = "STUDY_COMPARE_GRAPH_PAIR"
PAIR_SCHEMA_VERSION = 1
GRAPH_POLICY_VERSION = 2
DEFAULT_TIMEOUT_SECONDS = 900.0
DEFAULT_WORKERS = 4
TASK_PREFIXES = ("tutorial", "task-1", "task-2", "task-3")
_PUBLIC_PREFIX = {
    "tutorial": "practice",
    "task-1": "task-1",
    "task-2": "task-2",
    "task-3": "task-3",
}
_DESCRIPTION_NAME = {
    "tutorial": "practice/description",
    "task-1": "task-1/description",
    "task-2": "task-2/description",
    "task-3": "task-3/description",
}


class StudyCompareGraphPrewarmError(RuntimeError):
    """The hidden graph plan, provider result, or persisted cache is unsafe."""


class _Provider(Protocol):
    identity: ProviderIdentity

    def complete(
        self,
        prompt: str,
        *,
        operation: str,
        output_schema: dict[str, object] | None = None,
    ) -> str: ...


@dataclass(frozen=True)
class GraphView:
    task: str
    name: str
    context: Context
    context_digest: str
    memory_uids: tuple[str, ...]
    memory_contents: tuple[str, ...]
    memory_content_digests: tuple[str, ...]

    def manifest_record(self) -> dict[str, object]:
        return {
            "name": self.name,
            "context_uid": self.context.uid,
            "context_digest": self.context_digest,
            "include_descendants": True,
            "memory_count": len(self.memory_uids),
            "memory_uids": list(self.memory_uids),
            "memory_content_digests": list(self.memory_content_digests),
        }


@dataclass(frozen=True)
class GraphPair:
    task: str
    description_digest: str
    left: GraphView
    right: GraphView
    key: str


@dataclass(frozen=True)
class TaskGraphPlan:
    task: str
    description_name: str
    description_digest: str
    views: tuple[GraphView, ...]
    pairs: tuple[GraphPair, ...]


def _json(value: object, *, pretty: bool = False) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        sort_keys=True,
    )


def _sha(value: str | bytes) -> str:
    encoded = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(encoded).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _atomic_write_json(path: Path, value: Mapping[str, object]) -> None:
    if path.exists() and (not path.is_file() or path.is_symlink()):
        raise StudyCompareGraphPrewarmError(f"Unsafe cache path: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.write-{uuid.uuid4().hex}")
    try:
        with temporary.open("x", encoding="utf-8") as file:
            file.write(_json(value, pretty=True))
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result


def _read_json(path: Path) -> dict[str, object]:
    try:
        with path.open(encoding="utf-8") as file:
            value = json.load(file, object_pairs_hook=_strict_object)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise StudyCompareGraphPrewarmError(
            f"Cannot read hidden graph artifact: {path}"
        ) from error
    if not isinstance(value, dict):
        raise StudyCompareGraphPrewarmError(f"Invalid graph artifact: {path}")
    return value


def _view(task: str, context: Context) -> GraphView:
    memories = tuple(item for item in context.iter_items() if isinstance(item, Memory))
    return GraphView(
        task=task,
        name=context.name,
        context=context,
        context_digest=context_record_digest(context),
        memory_uids=tuple(memory.uid for memory in memories),
        memory_contents=tuple(memory.content for memory in memories),
        memory_content_digests=tuple(_sha(memory.content) for memory in memories),
    )


def _canonical_tutorial_views() -> tuple[GraphView, ...]:
    root, description, source = _study_practice_contexts()
    # The constructor returns storage records. Compose the descendant view in
    # memory so an older active Study run cannot silently restore the former
    # tutorial prose while this fixed fixture is being prewarmed.
    root.add(description)
    root.add(source)
    return (
        _view("tutorial", recursive_comparison_projection(root)),
        _view("tutorial", description),
        _view("tutorial", source),
    )


def _catalog_views(
    catalog: ReadableContextCatalog,
    task: str,
) -> tuple[GraphView, ...]:
    prefix = _PUBLIC_PREFIX[task]
    names = tuple(
        name
        for name in catalog.list_context_names()
        if name == prefix or name.startswith(prefix + "/")
    )
    if not names:
        raise StudyCompareGraphPrewarmError(f"No readable views for {task}.")
    return tuple(
        _view(
            task,
            load_comparison_context(
                catalog.access_for(name),
                include_descendants=True,
            ),
        )
        for name in names
    )


def _pair_key(
    *,
    task: str,
    description_digest: str,
    left: GraphView,
    right: GraphView,
    model: str,
    reasoning: str,
) -> str:
    value = {
        "task": task,
        "description_digest": description_digest,
        "operation": "COMPARE",
        "left": {"name": left.name, "digest": left.context_digest},
        "right": {"name": right.name, "digest": right.context_digest},
        "scope": ["INCLUDE_DESCENDANTS", "INCLUDE_DESCENDANTS"],
        "ruleset_version": COMPARISON_RULESET_VERSION,
        "compact_prompt_version": COMPACT_PROMPT_VERSION,
        "graph_policy_version": GRAPH_POLICY_VERSION,
        "provider": CODEX_CHATGPT_PROVIDER,
        "model": model,
        "reasoning": reasoning,
    }
    return _sha(_json(value))


def build_graph_plan(
    catalog: ReadableContextCatalog,
    *,
    model: str,
    reasoning: str,
    tasks: Sequence[str] = TASK_PREFIXES,
) -> tuple[TaskGraphPlan, ...]:
    requested = tuple(tasks)
    if not requested or any(task not in TASK_PREFIXES for task in requested):
        raise StudyCompareGraphPrewarmError("Unknown or empty Study task set.")
    if len(requested) != len(set(requested)):
        raise StudyCompareGraphPrewarmError("Study tasks must be unique.")
    plans: list[TaskGraphPlan] = []
    for task in requested:
        views = (
            _canonical_tutorial_views()
            if task == "tutorial"
            else _catalog_views(catalog, task)
        )
        by_name = {view.name: view for view in views}
        description_name = _DESCRIPTION_NAME[task]
        try:
            description = by_name[description_name]
        except KeyError as error:
            raise StudyCompareGraphPrewarmError(
                f"{task} has no fixed description view."
            ) from error
        pairs = tuple(
            GraphPair(
                task=task,
                description_digest=description.context_digest,
                left=left,
                right=right,
                key=_pair_key(
                    task=task,
                    description_digest=description.context_digest,
                    left=left,
                    right=right,
                    model=model,
                    reasoning=reasoning,
                ),
            )
            for left, right in itertools.combinations(views, 2)
        )
        plans.append(
            TaskGraphPlan(
                task=task,
                description_name=description_name,
                description_digest=description.context_digest,
                views=views,
                pairs=pairs,
            )
        )
    return tuple(plans)


def _member_record(
    analysis: ComparisonAnalysis,
    member: ComparisonMember,
) -> dict[str, str]:
    side_by_frame = {
        analysis.frames[0].uid: "LEFT",
        analysis.frames[1].uid: "RIGHT",
    }
    return {
        "side": side_by_frame[member.frame_uid],
        "memory_uid": member.memory_uid,
    }


def _compact_artifact(
    pair: GraphPair,
    analysis: ComparisonAnalysis,
    *,
    method: str,
    provider_evidence: Mapping[str, object] | None,
) -> dict[str, object]:
    relation_key_by_uid = {
        relation.uid: f"r{ordinal:06d}"
        for ordinal, relation in enumerate(analysis.relations, start=1)
    }
    relations = [
        {
            "relation_key": relation_key_by_uid[relation.uid],
            "kind": relation.kind,
            "status": relation.status,
            "members": [
                _member_record(analysis, member) for member in relation.members
            ],
            "comment": (
                ""
                if "no separate provider note was required" in relation.reason
                else relation.reason
            ),
        }
        for relation in analysis.relations
    ]
    issues = [
        {
            "priority": issue.priority,
            "relation_keys": [relation_key_by_uid[uid] for uid in issue.relation_uids],
            "title": issue.title,
            "question": issue.question,
            "why_it_matters": issue.why_it_matters,
            "options": [option.to_dict() for option in issue.options],
        }
        for issue in analysis.issues
    ]
    evidence = dict(provider_evidence or {})
    for private in (
        "raw_response",
        "normalized_analysis",
        "_captured_prompt",
        "prompt_digest",
        "schema_digest",
        "response_digest",
    ):
        evidence.pop(private, None)
    return {
        "kind": PAIR_KIND,
        "schema_version": PAIR_SCHEMA_VERSION,
        "pair_key": pair.key,
        "task": pair.task,
        "description_digest": pair.description_digest,
        "operation": "COMPARE",
        "state": "EXACT_PREWARM",
        "method": method,
        "created_at": _utc_now(),
        "left": {
            "name": pair.left.name,
            "context_uid": pair.left.context.uid,
            "context_digest": pair.left.context_digest,
            "memory_count": len(pair.left.memory_uids),
        },
        "right": {
            "name": pair.right.name,
            "context_uid": pair.right.context.uid,
            "context_digest": pair.right.context_digest,
            "memory_count": len(pair.right.memory_uids),
        },
        "relations": relations,
        "issues": issues,
        "coverage": {
            "expected": len(pair.left.memory_uids) + len(pair.right.memory_uids),
            "observed": sum(len(relation["members"]) for relation in relations),
        },
        "provider": evidence,
        "semantic_content_in_participant_report": False,
    }


def _empty_pair_artifact(pair: GraphPair) -> dict[str, object]:
    relations: list[dict[str, object]] = []
    ordinal = 0
    for side, view in (("LEFT", pair.left), ("RIGHT", pair.right)):
        for memory_uid in view.memory_uids:
            ordinal += 1
            relations.append(
                {
                    "relation_key": f"r{ordinal:06d}",
                    "kind": "DISTINCT",
                    "status": "RESOLVED",
                    "members": [{"side": side, "memory_uid": memory_uid}],
                    "comment": "",
                }
            )
    return {
        "kind": PAIR_KIND,
        "schema_version": PAIR_SCHEMA_VERSION,
        "pair_key": pair.key,
        "task": pair.task,
        "description_digest": pair.description_digest,
        "operation": "COMPARE",
        "state": "EXACT_PREWARM",
        "method": "DETERMINISTIC_EMPTY_VIEW",
        "created_at": _utc_now(),
        "left": {
            "name": pair.left.name,
            "context_uid": pair.left.context.uid,
            "context_digest": pair.left.context_digest,
            "memory_count": len(pair.left.memory_uids),
        },
        "right": {
            "name": pair.right.name,
            "context_uid": pair.right.context.uid,
            "context_digest": pair.right.context_digest,
            "memory_count": len(pair.right.memory_uids),
        },
        "relations": relations,
        "issues": [],
        "coverage": {"expected": len(relations), "observed": len(relations)},
        "provider": {"provider_calls": 0, "provider_seconds": 0.0},
        "semantic_content_in_participant_report": False,
    }


def _identity_containment(pair: GraphPair) -> bool:
    left = set(pair.left.memory_uids)
    right = set(pair.right.memory_uids)
    if not left or not right or not left.intersection(right):
        return False
    if not (left <= right or right <= left):
        return False
    left_contents = dict(
        zip(
            pair.left.memory_uids,
            pair.left.memory_contents,
            strict=True,
        )
    )
    right_contents = dict(
        zip(
            pair.right.memory_uids,
            pair.right.memory_contents,
            strict=True,
        )
    )

    def unqualified(content: str) -> str:
        # Recursive Compare prefixes a descendant's owner path solely to keep
        # provenance visible. The durable UID still names the same Memory when
        # the leaf view exposes the unprefixed content.
        if content.startswith("[") and "] " in content:
            return content.split("] ", 1)[1]
        return content

    return all(
        unqualified(left_contents[uid]) == unqualified(right_contents[uid])
        for uid in left.intersection(right)
    )


def _identity_containment_artifact(pair: GraphPair) -> dict[str, object]:
    left = set(pair.left.memory_uids)
    right = set(pair.right.memory_uids)
    relations: list[dict[str, object]] = []
    ordinal = 0
    for memory_uid in pair.left.memory_uids:
        ordinal += 1
        shared = memory_uid in right
        relations.append(
            {
                "relation_key": f"r{ordinal:06d}",
                "kind": "EQUIVALENT" if shared else "DISTINCT",
                "status": "RESOLVED",
                "members": (
                    [
                        {"side": "LEFT", "memory_uid": memory_uid},
                        {"side": "RIGHT", "memory_uid": memory_uid},
                    ]
                    if shared
                    else [{"side": "LEFT", "memory_uid": memory_uid}]
                ),
                "comment": "",
            }
        )
    for memory_uid in pair.right.memory_uids:
        if memory_uid in left:
            continue
        ordinal += 1
        relations.append(
            {
                "relation_key": f"r{ordinal:06d}",
                "kind": "DISTINCT",
                "status": "RESOLVED",
                "members": [{"side": "RIGHT", "memory_uid": memory_uid}],
                "comment": "",
            }
        )
    expected = len(pair.left.memory_uids) + len(pair.right.memory_uids)
    observed = sum(len(relation["members"]) for relation in relations)
    if observed != expected:
        raise StudyCompareGraphPrewarmError(
            "Identity containment did not preserve exact pair coverage."
        )
    return {
        "kind": PAIR_KIND,
        "schema_version": PAIR_SCHEMA_VERSION,
        "pair_key": pair.key,
        "task": pair.task,
        "description_digest": pair.description_digest,
        "operation": "COMPARE",
        "state": "EXACT_PREWARM",
        "method": "DETERMINISTIC_IDENTITY_CONTAINMENT",
        "created_at": _utc_now(),
        "left": {
            "name": pair.left.name,
            "context_uid": pair.left.context.uid,
            "context_digest": pair.left.context_digest,
            "memory_count": len(pair.left.memory_uids),
        },
        "right": {
            "name": pair.right.name,
            "context_uid": pair.right.context.uid,
            "context_digest": pair.right.context_digest,
            "memory_count": len(pair.right.memory_uids),
        },
        "relations": relations,
        "issues": [],
        "coverage": {"expected": expected, "observed": observed},
        "provider": {"provider_calls": 0, "provider_seconds": 0.0},
        "semantic_content_in_participant_report": False,
    }


def compute_pair(
    pair: GraphPair,
    provider: _Provider | None,
) -> dict[str, object]:
    if not pair.left.memory_uids or not pair.right.memory_uids:
        return _empty_pair_artifact(pair)
    if _identity_containment(pair):
        # The same durable Memory UID with the same content digest is stronger
        # evidence than a stochastic restatement judgment. In a containment
        # pair, every unmatched item is necessarily one-sided after those
        # identity matches are consumed.
        return _identity_containment_artifact(pair)
    if provider is None:
        raise StudyCompareGraphPrewarmError(
            "A nonempty Compare pair requires a semantic provider."
        )

    comparison_input = ComparisonInput.from_contexts(
        pair.left.context,
        pair.right.context,
        reference_descendants=True,
        compared_descendants=True,
    )
    result = run_compact_compare(provider, comparison_input, clock=time.monotonic)
    if result.analysis is None:
        evidence = result.evidence
        compact_reason = (
            evidence.get("validation_error")
            or evidence.get("error_type")
            or "unknown compact failure"
        )
        fallback_started = time.monotonic()
        fallback = analyze_comparison(comparison_input, provider)
        fallback_seconds = max(0.0, time.monotonic() - fallback_started)
        compact_seconds = evidence.get("provider_seconds", 0.0)
        compact_seconds = (
            float(compact_seconds) if isinstance(compact_seconds, (int, float)) else 0.0
        )
        return _compact_artifact(
            pair,
            fallback,
            method="COMPACT_FALLBACK_EXHAUSTIVE_V1",
            provider_evidence={
                "condition": "COMPACT_WITH_EXHAUSTIVE_FALLBACK",
                "provider_calls": 2,
                "provider_seconds": compact_seconds + fallback_seconds,
                "compact_provider_seconds": compact_seconds,
                "fallback_provider_seconds": fallback_seconds,
                "compact_validation_error": str(compact_reason),
            },
        )
    return _compact_artifact(
        pair,
        result.analysis,
        method="COMPACT_DECISION_VECTOR_V1",
        provider_evidence={
            **result.evidence,
            "provider_calls": 1,
        },
    )


def project_pair_deletions(
    artifact: Mapping[str, object],
    deleted_memory_uids: set[str],
) -> dict[str, object]:
    """Project deletions while retaining an explicit non-fresh state label."""

    if artifact.get("kind") != PAIR_KIND:
        raise StudyCompareGraphPrewarmError("Not a task-local Compare pair.")
    raw_relations = artifact.get("relations")
    if not isinstance(raw_relations, list):
        raise StudyCompareGraphPrewarmError("Pair relations are invalid.")
    projected_relations: list[dict[str, object]] = []
    retained_keys: set[str] = set()
    for raw in raw_relations:
        if not isinstance(raw, dict):
            raise StudyCompareGraphPrewarmError("Pair relation is invalid.")
        members = raw.get("members")
        if not isinstance(members, list):
            raise StudyCompareGraphPrewarmError("Pair members are invalid.")
        surviving = [
            member
            for member in members
            if isinstance(member, dict)
            and member.get("memory_uid") not in deleted_memory_uids
        ]
        if not surviving:
            continue
        sides = {member.get("side") for member in surviving}
        relation = dict(raw)
        relation["members"] = surviving
        if relation.get("kind") != "DISTINCT" and len(sides) == 1:
            relation["kind"] = "DISTINCT"
            relation["status"] = "RESOLVED"
            relation["comment"] = ""
        key = relation.get("relation_key")
        if isinstance(key, str):
            retained_keys.add(key)
        projected_relations.append(relation)
    raw_issues = artifact.get("issues")
    projected_issues: list[dict[str, object]] = []
    if isinstance(raw_issues, list):
        for raw in raw_issues:
            if not isinstance(raw, dict):
                continue
            keys = raw.get("relation_keys")
            if not isinstance(keys, list):
                continue
            surviving_keys = [key for key in keys if key in retained_keys]
            if not surviving_keys:
                continue
            issue = dict(raw)
            issue["relation_keys"] = surviving_keys
            projected_issues.append(issue)
    result = dict(artifact)
    result["state"] = "PROJECTED_FROM_PREWARM"
    result["projected_at"] = _utc_now()
    result["deleted_memory_uids"] = sorted(deleted_memory_uids)
    result["relations"] = projected_relations
    result["issues"] = projected_issues
    observed = sum(
        len(relation["members"])
        for relation in projected_relations
        if isinstance(relation.get("members"), list)
    )
    result["coverage"] = {"expected": observed, "observed": observed}
    return result


def _manifest(
    plans: Sequence[TaskGraphPlan],
    *,
    profile_name: str,
    profile_uid: str,
    model: str,
    reasoning: str,
) -> dict[str, object]:
    return {
        "kind": KIND,
        "schema_version": SCHEMA_VERSION,
        "created_at": _utc_now(),
        "profile_name": profile_name,
        "profile_uid": profile_uid,
        "provider": CODEX_CHATGPT_PROVIDER,
        "model": model,
        "reasoning": reasoning,
        "ruleset_version": COMPARISON_RULESET_VERSION,
        "compact_prompt_version": COMPACT_PROMPT_VERSION,
        "graph_policy_version": GRAPH_POLICY_VERSION,
        "scope": "INCLUDE_DESCENDANTS",
        "cross_task_pairs": False,
        "participant_report_visible": False,
        "tasks": [
            {
                "task": plan.task,
                "description_name": plan.description_name,
                "description_digest": plan.description_digest,
                "view_count": len(plan.views),
                "pair_count": len(plan.pairs),
                "views": [view.manifest_record() for view in plan.views],
            }
            for plan in plans
        ],
    }


def _pair_path(root: Path, pair: GraphPair) -> Path:
    return root / pair.task / "pairs" / f"{pair.key}.json"


def _failure_path(root: Path, pair: GraphPair) -> Path:
    return root / pair.task / "failures" / f"{pair.key}.json"


def _validate_existing_pair(path: Path, pair: GraphPair) -> dict[str, object]:
    artifact = _read_json(path)
    if (
        artifact.get("kind") != PAIR_KIND
        or artifact.get("schema_version") != PAIR_SCHEMA_VERSION
        or artifact.get("pair_key") != pair.key
        or artifact.get("task") != pair.task
        or artifact.get("description_digest") != pair.description_digest
        or artifact.get("state") != "EXACT_PREWARM"
    ):
        raise StudyCompareGraphPrewarmError(
            f"Existing pair does not match the frozen plan: {path}"
        )
    coverage = artifact.get("coverage")
    if not isinstance(coverage, dict) or coverage.get("expected") != coverage.get(
        "observed"
    ):
        raise StudyCompareGraphPrewarmError(
            f"Existing pair has incomplete coverage: {path}"
        )
    return artifact


def run_graph_prewarm(
    plans: Sequence[TaskGraphPlan],
    *,
    output_root: Path,
    provider_factory: Callable[[], _Provider],
    profile_name: str,
    profile_uid: str,
    model: str,
    reasoning: str,
    workers: int = DEFAULT_WORKERS,
    retries: int = 1,
    progress: Callable[[str], None] | None = None,
) -> dict[str, object]:
    if workers < 1 or retries < 0:
        raise StudyCompareGraphPrewarmError("Invalid worker or retry count.")
    output_root.mkdir(parents=True, exist_ok=True)
    manifest = _manifest(
        plans,
        profile_name=profile_name,
        profile_uid=profile_uid,
        model=model,
        reasoning=reasoning,
    )
    manifest_path = output_root / "manifest.json"
    if manifest_path.exists():
        previous = _read_json(manifest_path)
        stable_fields = (
            "kind",
            "schema_version",
            "profile_name",
            "profile_uid",
            "provider",
            "model",
            "reasoning",
            "ruleset_version",
            "compact_prompt_version",
            "graph_policy_version",
            "scope",
            "cross_task_pairs",
            "participant_report_visible",
            "tasks",
        )
        if any(previous.get(field) != manifest.get(field) for field in stable_fields):
            raise StudyCompareGraphPrewarmError(
                "Existing graph manifest does not match this frozen plan."
            )
    else:
        _atomic_write_json(manifest_path, manifest)

    all_pairs = tuple(pair for plan in plans for pair in plan.pairs)
    reused: list[dict[str, object]] = []
    pending: list[GraphPair] = []
    for pair in all_pairs:
        path = _pair_path(output_root, pair)
        if path.exists():
            reused.append(_validate_existing_pair(path, pair))
        else:
            pending.append(pair)
    if progress is not None:
        progress(
            f"PLAN views={sum(len(plan.views) for plan in plans)} "
            f"pairs={len(all_pairs)} reused={len(reused)} pending={len(pending)}"
        )

    local = threading.local()

    def provider() -> _Provider:
        value = getattr(local, "provider", None)
        if value is None:
            value = provider_factory()
            local.provider = value
        return value

    def execute(pair: GraphPair) -> dict[str, object]:
        last_error: BaseException | None = None
        for attempt in range(retries + 1):
            try:
                artifact = compute_pair(
                    pair,
                    provider()
                    if pair.left.memory_uids
                    and pair.right.memory_uids
                    and not _identity_containment(pair)
                    else None,
                )
                _atomic_write_json(_pair_path(output_root, pair), artifact)
                failure_path = _failure_path(output_root, pair)
                if failure_path.exists():
                    failure_path.unlink()
                return artifact
            except BaseException as error:
                last_error = error
                if attempt == retries:
                    _atomic_write_json(
                        _failure_path(output_root, pair),
                        {
                            "kind": "STUDY_COMPARE_GRAPH_PAIR_FAILURE",
                            "schema_version": 1,
                            "created_at": _utc_now(),
                            "pair_key": pair.key,
                            "task": pair.task,
                            "left": pair.left.name,
                            "right": pair.right.name,
                            "error_type": type(error).__name__,
                            "error": str(error),
                            "attempt_count": retries + 1,
                        },
                    )
                    raise
        assert last_error is not None
        raise last_error

    started = time.monotonic()
    completed = list(reused)
    failures: list[dict[str, str]] = []
    future_by_pair: dict[Future[dict[str, object]], GraphPair] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        queue = iter(pending)
        for pair in itertools.islice(queue, workers):
            future_by_pair[pool.submit(execute, pair)] = pair
        while future_by_pair:
            done, _ = wait(future_by_pair, return_when=FIRST_COMPLETED)
            for future in done:
                pair = future_by_pair.pop(future)
                try:
                    artifact = future.result()
                except BaseException as error:
                    failures.append(
                        {
                            "pair_key": pair.key,
                            "task": pair.task,
                            "left": pair.left.name,
                            "right": pair.right.name,
                            "error_type": type(error).__name__,
                            "error": str(error),
                        }
                    )
                else:
                    completed.append(artifact)
                failed_now = future.exception() is not None
                if progress is not None and (
                    len(completed) % 10 == 0
                    or len(completed) + len(failures) == len(all_pairs)
                    or failed_now
                ):
                    progress(
                        f"PROGRESS complete={len(completed)}/{len(all_pairs)} "
                        f"failed={len(failures)} task={pair.task} "
                        f"pair={pair.left.name}<>{pair.right.name}"
                    )
                try:
                    next_pair = next(queue)
                except StopIteration:
                    continue
                future_by_pair[pool.submit(execute, next_pair)] = next_pair

    elapsed = max(0.0, time.monotonic() - started)
    method_counts = Counter(str(item.get("method")) for item in completed)
    task_counts = Counter(str(item.get("task")) for item in completed)
    provider_seconds = sum(
        float(provider_record.get("provider_seconds", 0.0))
        for item in completed
        for provider_record in (item.get("provider"),)
        if isinstance(provider_record, dict)
        and isinstance(provider_record.get("provider_seconds", 0.0), (int, float))
    )
    summary = {
        "kind": "STUDY_COMPARE_GRAPH_PREWARM_SUMMARY",
        "schema_version": 1,
        "created_at": _utc_now(),
        "profile_name": profile_name,
        "profile_uid": profile_uid,
        "output_root": str(output_root),
        "view_count": sum(len(plan.views) for plan in plans),
        "pair_count": len(all_pairs),
        "completed_count": len(completed),
        "reused_count": len(reused),
        "failed_count": len(failures),
        "task_completed_counts": dict(sorted(task_counts.items())),
        "method_counts": dict(sorted(method_counts.items())),
        "workers": workers,
        "retries": retries,
        "provider_seconds": provider_seconds,
        "elapsed_seconds": elapsed,
        "failures": failures,
        "participant_report_visible": False,
    }
    _atomic_write_json(output_root / "summary.json", summary)
    return summary


def _default_output_root(profile_name: str, model: str, reasoning: str) -> Path:
    safe_model = model.replace("/", "-")
    return (
        Path("agent-records")
        / "outputs"
        / "study-compare-graph-prewarm"
        / profile_name
        / (
            f"{safe_model}-{reasoning}-compact-v{COMPACT_PROMPT_VERSION}"
            f"-graph-v{GRAPH_POLICY_VERSION}"
        )
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prewarm every within-task Study Compare view pair."
    )
    parser.add_argument(
        "--task",
        action="append",
        choices=TASK_PREFIXES,
        dest="tasks",
    )
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--reasoning",
        choices=CODEX_REASONING_EFFORTS,
        default=None,
    )
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--plan-only", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if (
        (args.timeout is not None and args.timeout <= 0)
        or args.workers < 1
        or args.retries < 0
    ):
        print(
            "Timeout/workers must be positive and retries nonnegative.", file=sys.stderr
        )
        return 2
    config = Config()
    policy = resolve_codex_evaluation_policy(
        "compare_contexts",
        config=config,
        model=args.model,
        reasoning_effort=args.reasoning,
        timeout_seconds=args.timeout,
    )
    model = policy.model
    reasoning = policy.reasoning_effort
    if not model:
        print("No Codex model configured; pass --model explicitly.", file=sys.stderr)
        return 2
    assert reasoning is not None
    try:
        registry = load_profile_registry()
        store = MemoryStore(create=False)
        current = store.current_context_name()
        selected = resolve_context_access(
            store,
            current,
            current_name=current,
            required_permission="READ",
            registry=registry,
        )
        catalog = freeze_profile_readable_context_catalog(store, selected)
        plans = build_graph_plan(
            catalog,
            model=model,
            reasoning=reasoning,
            tasks=args.tasks or TASK_PREFIXES,
        )
        output_root = args.output_root or _default_output_root(
            registry.active.name,
            model,
            reasoning,
        )
        plan_summary = {
            "output_root": str(output_root),
            "profile_name": registry.active.name,
            "model": model,
            "reasoning": reasoning,
            "tasks": [
                {
                    "task": plan.task,
                    "views": len(plan.views),
                    "pairs": len(plan.pairs),
                    "provider_pairs": sum(
                        bool(
                            pair.left.memory_uids
                            and pair.right.memory_uids
                            and not _identity_containment(pair)
                        )
                        for pair in plan.pairs
                    ),
                }
                for plan in plans
            ],
            "views": sum(len(plan.views) for plan in plans),
            "pairs": sum(len(plan.pairs) for plan in plans),
        }
        print(_json({"plan": plan_summary}, pretty=True), flush=True)
        if args.plan_only:
            return 0

        def provider_factory() -> _Provider:
            return CodexChatGPTProvider.connect(
                timeout=policy.timeout_seconds,
                model=model,
                reasoning_effort=reasoning,
            )

        summary = run_graph_prewarm(
            plans,
            output_root=output_root,
            provider_factory=provider_factory,
            profile_name=registry.active.name,
            profile_uid=registry.active.uid,
            model=model,
            reasoning=reasoning,
            workers=args.workers,
            retries=args.retries,
            progress=lambda message: print(message, flush=True),
        )
    except Exception as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(_json(summary, pretty=True))
    return 0 if summary["failed_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
