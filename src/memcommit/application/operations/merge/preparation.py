"""Freeze Merge endpoints and prepare structural findings and fixed choices."""

from __future__ import annotations

import json
import uuid

from memcommit.application.authorization.context_operation import (
    authorized_context_operation,
)
from memcommit.application.capabilities.history.reconstruction.memory_lineage_relations import (
    checkpoint_memory_lineage_edges,
    resolve_lineage_target_uids,
)
from memcommit.application.context_access.access import ContextAccess, GrantedReadStore
from memcommit.application.context_access.operand_resolution import (
    freeze_profile_context_access_candidates,
    resolve_existing_context_access,
)
from memcommit.core.context import Context, Memory
from memcommit.persistence.store import MemoryStore, context_record_digest
from memcommit.persistence.store.infrastructure.write_protection import (
    WriteProtectionError,
)

from .analysis.candidate import combine_contexts, encode
from .analysis.choices import (
    MergeConflictAnalysis,
    MergeConflictIssue,
    merge_item_kind,
    prepare_structural_input,
)
from .analysis.conflicts import analyze_merge_conflicts
from .inputs import LiteralMergeInput, MergeContextInputs, MergeRequest, PreparedMerge
from .result import LiteralMergeReview
from .setup import merge_target_permission
from .target_policy import MergeTargetPolicy


def prepare_merge(
    request: MergeRequest, *, store: MemoryStore, current_name: str | None
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
    request: MergeRequest, *, store: MemoryStore, current_name: str | None
) -> MergeContextInputs:
    """Load direct endpoints once and retain the verified publication conditions."""
    candidates = freeze_profile_context_access_candidates(
        store, current_name=current_name
    )
    source_access = resolve_existing_context_access(
        store,
        request.source,
        current_name=current_name,
        required_permission="READ",
        candidates=candidates,
    ).value
    target_access = resolve_existing_context_access(
        store,
        request.target,
        current_name=current_name,
        required_permission=merge_target_permission(request.method),
        candidates=candidates,
    ).value
    with authorized_context_operation(
        (
            (source_access, ("READ",)),
            (target_access, (merge_target_permission(request.method),)),
        )
    ):
        source = (
            GrantedReadStore(source_access).load_direct(source_access.access_name)
            if source_access.is_granted
            else source_access.store.load_for_update(source_access.context_name)
        )
        target = target_access.store.load_for_update(target_access.context_name)
        raw_target_digest = target._store_digest or context_record_digest(target)
        if target_access.is_granted:
            visible = GrantedReadStore(target_access).project_direct(
                target, target_access.access_name
            )
            if visible.to_dict()["memories"] != target.to_dict()["memories"]:
                raise ValueError(
                    "Merge Target has hidden direct items; its readable view cannot replace the full record."
                )
            target = visible
        if (
            source.uid == target.uid
            and source_access.store.store_dir == target_access.store.store_dir
        ):
            raise ValueError("cannot merge a context into itself.")
        mutable, protected = _target_plan_protection(target_access, target)
        source_digest = context_record_digest(source)
        cross_profile = source_access.store.store_dir != target_access.store.store_dir
        projected_source = _memory_only_source(source) if cross_profile else source
        lineage = _lineage_target_uids(
            source_access, target_access, projected_source, target
        )
        effects = tuple(
            value
            for value in ("CREATE", "UPDATE", "DELETE")
            if target_access.view is None
            or value in target_access.view.grant.permissions
        )
        projected_source.name, target.name = (
            source_access.access_name,
            target_access.access_name,
        )
        return MergeContextInputs(
            operation_uid=str(uuid.uuid4()),
            source_json=encode(projected_source.to_dict()),
            target_json=encode(target.to_dict()),
            source_digest=source_digest,
            target_digest=raw_target_digest,
            source_access=source_access,
            target_access=target_access,
            policy=MergeTargetPolicy(effects, mutable, protected),
            lineage_targets=tuple(lineage.items()),
            cross_profile_memory_only=cross_profile,
        )


def _memory_only_source(source: Context) -> Context:
    """Copy portable Memory values without carrying cross-Profile pointers."""

    result = Context(uid=source.uid, name=source.name)
    for item in source.iter_items():
        if isinstance(item, Memory):
            result.add(Memory(uid=item.uid, content=item.content))
    return result


def _target_plan_protection(
    access: ContextAccess,
    target: Context,
) -> tuple[bool, frozenset[str]]:
    """Freeze the Target policy that determines reviewable replacements."""

    state = access.store.write_protection_state()
    if state.profile_is_protected():
        raise WriteProtectionError(
            "Profile is locked against writes. Unlock that Profile first."
        )
    return (
        not state.context_is_protected(target.uid),
        state.protected_memory_uids(target.uid),
    )


def _lineage_target_uids(
    source_access: ContextAccess,
    target_access: ContextAccess,
    source: Context,
    target: Context,
) -> dict[str, str]:
    """Resolve only same-Store ordinary lineage retained by both histories."""

    if (
        source_access.is_granted
        or target_access.is_granted
        or source_access.store.store_dir != target_access.store.store_dir
    ):
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
        kinds = {merge_item_kind(candidate.original_item(uid)) for uid in members}
        issues.append(
            MergeConflictIssue(
                uid=finding.uid,
                classification=finding.kind.value,
                item_uids=members,
                item_kind=next(iter(kinds)) if len(kinds) == 1 else "MIXED",
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
