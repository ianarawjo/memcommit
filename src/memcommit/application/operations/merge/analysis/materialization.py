"""Calculate choice post-images and occurrence mappings without saving them."""

from memcommit.core.context import Context, Memory

from ..inputs import StructuralResolutionInput
from .candidate import copy_direct_context, copy_direct_item
from .choices import (
    EXACT_DECISIONS,
    MergeConflictAnalysis,
    MergeDecisionSet,
    merge_sides,
)


def materialize_structural_choices(
    analysis: MergeConflictAnalysis,
    decisions: MergeDecisionSet,
    inputs: StructuralResolutionInput,
) -> Context:
    """Apply exact choices without semantic planning or durable publication."""
    if inputs.revision != analysis.revision or decisions.revision != inputs.revision:
        raise ValueError("Structural choices no longer match the frozen revision.")
    report, candidate = analysis.report, analysis.candidate
    source, target = inputs.source(), inputs.target()
    for frame, context in zip(candidate.frame_order, (target, source), strict=True):
        if tuple(
            origin.record() for origin in candidate.origins if origin.frame == frame
        ) != tuple(
            context.to_dict()["memories"][uid] for uid in context.ordered_uids()
        ):
            raise ValueError("Structural input changed its frozen original items.")
    issues = {issue.uid: issue for issue in analysis.review_issues}
    if tuple(item.source_uid for item in inputs.additions) != tuple(
        candidate.origin(uid).item_uid for uid in report.additions
    ) or tuple(item.issue_uid for item in inputs.conflicts) != tuple(
        item.uid for item in report.findings
    ):
        raise ValueError("Structural changes do not cover the frozen items.")
    for conflict, finding in zip(inputs.conflicts, report.findings, strict=True):
        if (
            conflict.source_uid != candidate.origin(finding.source_uid).item_uid
            or conflict.target_uids
            != tuple(candidate.origin(uid).item_uid for uid in finding.target_uids)
            or conflict.allowed_choices
            != tuple(choice.uid for choice in issues[conflict.issue_uid].choices)
        ):
            raise ValueError(
                "Structural choice changed its frozen members or availability."
            )

    result = copy_direct_context(target)
    for addition in inputs.additions:
        item = copy_direct_item(
            source.memories[addition.source_uid], memory_uid=addition.target_uid
        )
        if item.uid in result.memories:
            raise ValueError("Structural addition identity collides with the Target.")
        result.add(item)

    chosen = {decision.issue_uid: decision.kind for decision in decisions.decisions}
    for conflict in inputs.conflicts:
        decision = chosen[conflict.issue_uid]
        if decision not in conflict.allowed_choices:
            raise ValueError("Structural choice is unavailable for this issue.")
        if decision == "KEEP_TARGET":
            continue
        source_item = source.memories[conflict.source_uid]
        if decision == "KEEP_BOTH":
            # The caller freezes identity once; Preview and Apply must retain it.
            if (
                not isinstance(source_item, Memory)
                or not conflict.keep_both_uid
                or conflict.keep_both_uid in result.memories
            ):
                raise ValueError("Keep Both requires a fresh frozen Memory identity.")
            positions = [
                result.ordered_uids().index(uid) for uid in conflict.target_uids
            ]
            result.add(
                copy_direct_item(source_item, memory_uid=conflict.keep_both_uid),
                position=max(positions) + 1,
            )
            continue
        if decision != "TAKE_SOURCE":
            raise ValueError("Unknown structural choice.")
        positions = [
            result.ordered_uids().index(uid)
            for uid in conflict.target_uids
            if uid in result.memories
        ]
        for uid in conflict.target_uids:
            if uid in result.memories:
                result.remove(uid)
        result.add(
            copy_direct_item(
                source_item,
                memory_uid=_replacement_memory_uid(source_item, target, conflict),
            ),
            position=min(positions) if positions else None,
        )
    return result


def _replacement_memory_uid(source_item, target, conflict):
    # Only Memory-to-Memory replacement retains the Target occurrence identity.
    return (
        conflict.target_uids[0]
        if isinstance(source_item, Memory)
        and len(conflict.target_uids) == 1
        and isinstance(target.memories.get(conflict.target_uids[0]), Memory)
        else None
    )


def materialize_exact_decisions(analysis, decisions, target):
    record = Context.from_dict(target.to_dict())
    protected = {}
    issues = {issue.uid: issue for issue in analysis.review_issues}
    for decision in decisions.decisions:
        if decision.kind not in EXACT_DECISIONS:
            continue
        issue = issues[decision.issue_uid]
        members = issue.item_uids
        if issue.item_kind != "MEMORY":
            continue
        if any(not isinstance(target.memories.get(uid), Memory) for uid in members):
            raise ValueError(
                "Exact Memory choices require their frozen Memory members."
            )
        expected = {uid: target.memories[uid].content for uid in members}
        if decision.kind != "KEEP_BOTH":
            targets, sources = merge_sides(analysis.candidate, issue)
            if not targets or len(sources) != 1:
                raise ValueError(
                    "This issue does not identify one Source and a Target."
                )
            source_uid = sources[0]
            expected[source_uid] = None
            if decision.kind == "TAKE_SOURCE":
                expected[targets[0]] = target.memories[source_uid].content
                for uid in targets[1:]:
                    expected[uid] = None
        for uid, content in expected.items():
            if uid in protected and protected[uid] != content:
                raise ValueError(
                    "Overlapping exact choices disagree about a Memory. Revise the choices."
                )
            protected[uid] = content
            if content is None:
                if uid in record.memories:
                    record.remove(uid)
            elif content != record.memories[uid].content:
                record.replace_memory(Memory(uid, content))
    return record


def materialize_structural_result(analysis, finalized, structural_input):
    """Calculate detached content and its original-to-result occurrence mapping."""
    post_image = materialize_structural_choices(analysis, finalized, structural_input)
    # Check exact choices against the original endpoints. Rechecking the union
    # would reinterpret an explicitly accepted Keep Both as a fresh conflict.
    candidate = analysis.candidate
    choices = {decision.issue_uid: decision.kind for decision in finalized.decisions}
    copies = {item.source_uid: item.target_uid for item in structural_input.additions}
    copies.update(
        {
            item.source_uid: item.keep_both_uid
            for item in structural_input.conflicts
            if choices[item.issue_uid] == "KEEP_BOTH"
        }
    )
    source, target = structural_input.source(), structural_input.target()
    copies.update(
        {
            item.source_uid: _replacement_memory_uid(
                source.memories[item.source_uid], target, item
            )
            or item.source_uid
            for item in structural_input.conflicts
            if choices[item.issue_uid] == "TAKE_SOURCE"
        }
    )
    mappings = tuple(
        (
            origin.uid,
            origin.item_uid
            if origin.frame == candidate.frame_order[0]
            else copies[origin.item_uid] or origin.item_uid,
        )
        for origin in candidate.origins
        if origin.frame == candidate.frame_order[0] or origin.item_uid in copies
    )
    return post_image, mappings
