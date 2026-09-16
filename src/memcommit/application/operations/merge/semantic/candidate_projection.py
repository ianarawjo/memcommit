"""Read-only projection of a current Meld candidate and its Audit evidence."""

from memcommit.application.operations.merge.semantic.model import MeldSession
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionWorkbenchView,
    ResolutionMetric,
    ResolutionResult,
)
from memcommit.core.context import Memory


class MeldCandidateWorkbenchAdapter:
    def __init__(self, session: MeldSession):
        self.session = session

    def view(self) -> ResolutionWorkbenchView:
        session = self.session
        review = session.candidate_review
        if review is None:
            raise ValueError("Meld candidate review is unavailable.")
        route = f"{session.frames[0].context_name} + {session.frames[1].context_name} → {session.target.context_name}"
        overview = "Audit-backed candidate; Update and Source coverage verification precede Target publication."
        for issue in review.issues:
            overview += f"\n\n{issue.kind} · {issue.classification}\n{issue.reason}\n{issue.question}\n{issue.proposed_direction}"
        if review.forced_audit_keys:
            overview += "\n\nUNRESOLVED AUDIT ITEMS\n" + "\n".join(
                review.forced_audit_keys
            )
        return ResolutionWorkbenchView(
            operation="MELD",
            artifact_uid=session.uid,
            revision=review.revision,
            title=f"MEM MELD · {session.mode}",
            route=route,
            status=session.state,
            metrics=(
                ResolutionMetric("SOURCE CLAIMS", str(len(review.source_claims))),
                ResolutionMetric("AUDIT ITEMS", str(len(review.issues))),
                ResolutionMetric("UNRESOLVED", str(len(review.forced_audit_keys))),
            ),
            overview=overview,
            list_label="AUDIT ITEMS",
            items=(),
            empty_message="Resolve decisions belong to the Meld execution workflow.",
            results_label="VERIFIED RESULT MEMORIES"
            if session.state == "APPLIED"
            else "CANDIDATE MEMORIES",
            results=tuple(
                ResolutionResult(
                    uid=item.uid, marker="·", label="MEMORY", text=item.content
                )
                for item in review.candidate.iter_items()
                if isinstance(item, Memory)
            ),
            input_locked=True,
        )
