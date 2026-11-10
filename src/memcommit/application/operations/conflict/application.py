"""Analyze one frozen Context and derive its issue directions."""

from __future__ import annotations
import hashlib
import json
from typing import TYPE_CHECKING, Protocol
from memcommit.application.operations.audit.model import (
    AuditCheckKind,
    QualityAuditSession,
)
from memcommit.application.operations.audit.repository import AuditRecordRepository
from .model import (
    AuditResolutionIssue,
    ConflictResolutionTarget,
    ConflictResolutionAnalysis,
    ConflictTargetChangedError,
    ConflictResolutionReceipt,
    ConflictResolutionError,
)
from .analysis import reuse_or_run_audit
from .analysis.select_issues_for_review import (
    remaining_review_issues,
)

if TYPE_CHECKING:
    from .review_round.finalize_review_decisions import ConflictResolutionFinalizedInput
    from memcommit.application.operations.conflict.review_round.review_round_record import (
        ReviewRoundRecord,
    )
    from memcommit.application.operations.update.model import UpdatePlan
CONFLICT_RESOLUTION_CHECKS = frozenset({AuditCheckKind.CONFLICTS})


def analyze_conflicts_for_resolution(
    frame: ConflictResolutionTarget,
    *,
    checks: frozenset[AuditCheckKind],
    semantic_port: ConflictResolutionSemanticPort,
    audit_repository: AuditRecordRepository,
    audit_provider_factory: ConflictResolutionProviderFactory,
    direction_provider_factory: ConflictResolutionProviderFactory,
    expected_revision: str | None = None,
) -> ConflictResolutionAnalysis:
    """Acquire one exact Audit, then derive directions without applying them."""
    if checks != CONFLICT_RESOLUTION_CHECKS:
        raise ConflictResolutionError("Conflict requires conflicts-only checks.")
    _require_source_precondition(frame)
    if expected_revision is not None and expected_revision != frame.revision:
        raise ConflictTargetChangedError(
            "The Conflict Context or requested capability frame changed before its decisions could be finalized."
        )
    target = frame.source.context()
    audit = reuse_or_run_audit.audit_context_for_conflict_resolution(
        target,
        provider_factory=audit_provider_factory,
        repository=audit_repository,
        checks=checks,
    )
    analysis = derive_conflict_resolution_directions(
        frame,
        audit,
        semantic_port=semantic_port,
        direction_provider_factory=direction_provider_factory,
    )
    return analysis


def derive_conflict_resolution_directions(
    frame: ConflictResolutionTarget,
    audit: QualityAuditSession,
    *,
    semantic_port: ConflictResolutionSemanticPort,
    direction_provider_factory: ConflictResolutionProviderFactory,
    rounds: tuple[ReviewRoundRecord, ...] = (),
) -> ConflictResolutionAnalysis:
    """Derive decisions from an already acquired Audit; never apply them."""

    class LazyDirectionProvider:
        def complete(self, *args, **kwargs):
            return direction_provider_factory().complete(*args, **kwargs)

    provider = LazyDirectionProvider()
    issues = remaining_review_issues(audit, rounds=rounds, frame=frame)
    analysis = semantic_port.analyze(frame, audit, issues=issues, provider=provider)
    return analysis


def _require_source_precondition(frame: ConflictResolutionTarget) -> None:
    expected = frame.request.source_precondition
    if expected is None:
        return
    if (
        frame.source.context_uid != expected.context_uid
        or frame.display_name != expected.display_name
        or _direct_memory_digest(frame) != expected.direct_memory_digest
    ):
        raise ConflictTargetChangedError(
            "The quality finding source no longer matches the frozen Conflict Context. Run the finder again before resolving it."
        )


def _direct_memory_digest(frame: ConflictResolutionTarget) -> str:
    payload = [
        {"uid": memory.uid, "content": memory.content}
        for memory in frame.source.memories
    ]
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


class ConflictResolutionProvider(Protocol):
    """The bounded completion primitive used by Conflict semantic turns."""

    def complete(
        self,
        prompt: str,
        *,
        operation: str,
        output_schema: dict[str, object] | None = None,
    ) -> str:
        """Return one complete structured semantic response."""


class ConflictResolutionProviderFactory(Protocol):
    def __call__(self) -> ConflictResolutionProvider:
        """Connect after the complete local frame and authority are frozen."""


class ConflictResolutionApplyPort(Protocol):
    """Publish the final reviewed proposal; calculation needs no Store port."""

    def apply_update_plan(
        self,
        frame: ConflictResolutionTarget,
        plan: UpdatePlan,
        *,
        unresolved_issue_uids: tuple[str, ...] = (),
        finalized_inputs: tuple[ConflictResolutionFinalizedInput, ...] = (),
    ) -> ConflictResolutionReceipt:
        """Publish one Conflict-generated exact Update plan atomically."""


class ConflictResolutionSemanticPort(Protocol):
    def analyze(
        self,
        frame: ConflictResolutionTarget,
        audit: QualityAuditSession,
        *,
        issues: tuple[AuditResolutionIssue, ...],
        provider: ConflictResolutionProvider | None = None,
    ) -> ConflictResolutionAnalysis:
        """Generate one direction per selected issue, using the complete Context."""
