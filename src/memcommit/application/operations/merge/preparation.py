"""Freeze Merge endpoints and prepare structural findings and fixed choices."""

from __future__ import annotations

import json
import uuid

from memcommit.application.capabilities.history.reconstruction.memory_lineage_relations import (
    checkpoint_memory_lineage_edges,
    resolve_lineage_target_uids,
)
from memcommit.application.context_access.access import ContextAccess
from memcommit.application.context_access.operand_resolution import (
    freeze_profile_context_access_candidates,
    resolve_existing_context_access,
)
from memcommit.models.context import Context
from memcommit.persistence.store import ProfileStore

from .analysis.candidate import combine_contexts, encode
from .analysis.choices import (
    MergeConflictAnalysis,
    MergeConflictIssue,
    prepare_structural_input,
)
from .analysis.conflicts import analyze_merge_conflicts
from .inputs import LiteralMergeInput, MergeContextInputs, MergeRequest, PreparedMerge
from .result import LiteralMergeReview
from .target_policy import MergeTargetPolicy


def prepare_merge(
    request: MergeRequest, *, store: ProfileStore, current_name: str | None
) -> PreparedMerge:
    """Freeze one Source/Target pair; Resolve owns Audit and review preparation."""
    if not isinstance(request, MergeRequest):
        raise TypeError("Merge preparation requires a MergeRequest.")
    inputs = load_merge_context_inputs(request, store=store, current_name=current_name)
    return PreparedMerge(request, inputs, prepare_literal_input(request, inputs))


def prepare_literal_input(
    request: MergeRequest, inputs: MergeContextInputs
) -> LiteralMergeInput:
    """Bind the complete candidate to its exact endpoint and policy evidence."""
    source, target = inputs.source(), inputs.target()
    candidate = combine_contexts(
        (target, source),
        placement=target.name,
        identities={(1, uid): target_uid for uid, target_uid in inputs.lineage_targets},
    )
    return LiteralMergeInput(
        candidate=candidate,
        source_json=inputs.source_json,
        target_json=inputs.target_json,
        target_policy=inputs.policy,
        method=request.method,
        binding_digest=inputs.digest,
    )


def load_merge_context_inputs(
    request: MergeRequest, *, store: ProfileStore, current_name: str | None
) -> MergeContextInputs:
    """Load direct endpoints once and retain the verified publication conditions."""
    candidates = freeze_profile_context_access_candidates(
        store, current_name=current_name
    )
    source_access = resolve_existing_context_access(
        store,
        request.source,
        current_name=current_name,
        candidates=candidates,
    ).value
    target_access = resolve_existing_context_access(
        store,
        request.target,
        current_name=current_name,
        candidates=candidates,
    ).value
    source = source_access.store.load_for_update(source_access.context_name)
    target = target_access.store.load_for_update(target_access.context_name)
    if (
        source.uid == target.uid
        and source_access.store.store_dir == target_access.store.store_dir
    ):
        raise ValueError("cannot merge a context into itself.")
    projected_source = source
    lineage = _lineage_target_uids(source_access, target_access, source, target)
    effects = ("CREATE", "UPDATE", "DELETE")
    projected_source.name, target.name = (
        source_access.access_name,
        target_access.access_name,
    )
    return MergeContextInputs(
        operation_uid=str(uuid.uuid4()),
        source_json=encode(projected_source.to_dict()),
        target_json=encode(target.to_dict()),
        source_access=source_access,
        target_access=target_access,
        policy=MergeTargetPolicy(effects),
        lineage_targets=tuple(lineage.items()),
    )


def _lineage_target_uids(
    source_access: ContextAccess,
    target_access: ContextAccess,
    source: Context,
    target: Context,
) -> dict[str, str]:
    """Resolve only same-Store ordinary lineage retained by both histories."""

    if source_access.store.store_dir != target_access.store.store_dir:
        return {}
    edges = checkpoint_memory_lineage_edges(
        (
            source_access.store.list_checkpoints(source_access.context_name),
            target_access.store.list_checkpoints(target_access.context_name),
        )
    )
    return resolve_lineage_target_uids(source, target, edges)


def prepare_literal_merge(inputs: LiteralMergeInput):
    frozen = inputs.digest
    report = analyze_merge_conflicts(inputs.candidate)
    review = prepare_literal_review(
        inputs.candidate,
        report,
        source=Context.from_dict(json.loads(inputs.source_json)),
        target=Context.from_dict(json.loads(inputs.target_json)),
        policy=inputs.target_policy,
        input_digest=frozen,
        defer_target_validation=inputs.method == "SEMANTIC",
    )
    if inputs.digest != frozen:
        raise ValueError("Merge input changed while preparing its review.")
    return review


def prepare_literal_review(
    candidate,
    report,
    *,
    source,
    target,
    policy,
    input_digest=None,
    defer_target_validation=False,
):
    """Freeze exact choices and allocations directly from Merge's findings."""
    if report != analyze_merge_conflicts(candidate):
        raise ValueError("Merge conflict report does not match its candidate.")
    structure, choices = prepare_structural_input(
        candidate,
        report,
        source=source,
        target=target,
        revision=candidate.revision,
        policy=policy,
        defer_target_validation=defer_target_validation,
    )
    issues = []
    for finding in report.findings:
        members = (*finding.target_uids, finding.source_uid)
        issues.append(
            MergeConflictIssue(
                uid=finding.uid,
                classification=finding.kind.value,
                item_uids=members,
                item_kind="MEMORY",
                reason=finding.reason,
                choices=choices[finding.uid],
            )
        )
    return LiteralMergeReview(
        MergeConflictAnalysis(candidate, report, tuple(issues)),
        structure,
        policy,
        input_digest,
        defer_target_validation,
    )
