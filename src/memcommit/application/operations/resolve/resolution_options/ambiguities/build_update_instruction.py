"""Turn an accepted Ambiguity suggestion or Intent into an Update instruction."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...decisions import ResolveDecision
    from ...model import ResolveAnalysis, ResolveIssue


def build_update_instruction(
    analysis: ResolveAnalysis, issue: ResolveIssue, decision: ResolveDecision
) -> str:
    intended = (
        issue.proposed_direction
        if decision.kind == "CONFIRM"
        else decision.intent.strip()
    )
    members = ", ".join(issue.item_uids)
    by_uid = {item.uid: item.summary for item in analysis.frame.source.items}
    # Update exposes its own aliases, not these durable/candidate UIDs.
    # Include exact evidence so the direction can identify its members.
    evidence = "\n".join(f"[{uid}] {by_uid[uid]}" for uid in issue.item_uids)
    return (
        f"Resolution input for target Context {analysis.frame.display_name!r}.\n"
        f"Audit item {issue.uid!r} is {issue.kind} ({issue.classification})"
        f" and concerns target Memories [{members}].\n"
        f"Issue evidence:\n{evidence}\n"
        f"The accepted direction is: {intended}\n"
        "Update the complete target Context so this meaning is represented "
        "consistently, while preserving unrelated information."
    )
