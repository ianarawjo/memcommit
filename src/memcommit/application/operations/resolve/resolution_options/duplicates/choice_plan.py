"""Materialize the displayed duplicate choice without rewriting any Memory."""

from memcommit.application.operations.merge.analysis.candidate import digest
from memcommit.application.operations.update.model import RemoveOperation, UpdatePlan
from ...model import ResolveError


def duplicate_choice_plan(analysis, decisions, target) -> UpdatePlan:
    issues = {issue.uid: issue for issue in analysis.issues}
    removed = {}
    for decision in decisions.decisions:
        issue = issues[decision.issue_uid]
        if (
            issue.kind != "REDUNDANCY"
            or issue.item_kind != "MEMORY"
            or decision.kind != "CONFIRM"
        ):
            continue
        if "DELETE" not in analysis.frame.allowed_effects:
            raise ResolveError("Keeping one duplicate requires DELETE authority.")
        # Audit preserves the survivor first. Selecting KEEP ONE never licenses
        # a provider rewrite of that survivor or removal of unrelated content.
        for uid in issue.item_uids[1:]:
            removed[uid] = RemoveOperation(
                owner_context_uid=target.uid,
                owner_context_name=target.name,
                memory_uid=uid,
                old_content=target.memories[uid].content,
                source_refs=(),
                reason=issue.proposed_direction,
            )
    return UpdatePlan(
        "resolve-duplicates-" + digest([op.to_dict() for op in removed.values()]),
        target.uid,
        target.name,
        tuple(removed.values()),
    )
