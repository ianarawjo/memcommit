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
    ResolveTarget,
    ResolveAnalysis,
    ResolveConflictError,
    ResolveReceipt,
)
from .analysis import reuse_or_run_audit
from .analysis.select_issues_for_review import (
    remaining_review_issues,
    select_round_issues,
)

if TYPE_CHECKING:
    from .review_round.finalize_review_decisions import ResolveFinalizedInput
    from memcommit.application.operations.resolve.review_round.review_round_record import (
        ReviewRoundRecord,
    )
    from memcommit.application.operations.update.model import UpdatePlan
RESOLVE_CHECKS = frozenset({AuditCheckKind.CONFLICTS})


def run_resolve(
    frame: ResolveTarget,
    *,
    checks: frozenset[AuditCheckKind],
    semantic_port: ResolveSemanticPort,
    audit_repository: AuditRecordRepository,
    audit_provider_factory: ResolveProviderFactory,
    direction_provider_factory: ResolveProviderFactory,
    expected_revision: str | None = None,
) -> ResolveAnalysis:
    """Acquire one exact Audit, then derive directions without applying them."""
    _require_source_precondition(frame)
    if expected_revision is not None and expected_revision != frame.revision:
        raise ResolveConflictError(
            "The Resolve Context or requested capability frame changed before its decisions could be finalized."
        )
    target = frame.source.context()
    audit = reuse_or_run_audit.audit_resolve_context(
        target,
        provider_factory=audit_provider_factory,
        repository=audit_repository,
        checks=checks,
    )
    analysis = analyze_resolve_audit(
        frame,
        audit,
        semantic_port=semantic_port,
        direction_provider_factory=direction_provider_factory,
    )
    return analysis


def analyze_resolve_audit(
    frame: ResolveTarget,
    audit: QualityAuditSession,
    *,
    semantic_port: ResolveSemanticPort,
    direction_provider_factory: ResolveProviderFactory,
    rounds: tuple[ReviewRoundRecord, ...] = (),
) -> ResolveAnalysis:
    """Derive decisions from an already acquired Audit; never apply them."""

    class LazyDirectionProvider:
        def complete(self, *args, **kwargs):
            return direction_provider_factory().complete(*args, **kwargs)

    provider = LazyDirectionProvider()
    issues = select_round_issues(
        remaining_review_issues(audit, rounds=rounds, frame=frame)
    )
    analysis = semantic_port.analyze(frame, audit, issues=issues, provider=provider)
    return analysis


def _require_source_precondition(frame: ResolveTarget) -> None:
    expected = frame.request.source_precondition
    if expected is None:
        return
    if (
        frame.source.context_uid != expected.context_uid
        or frame.display_name != expected.display_name
        or _direct_memory_digest(frame) != expected.direct_memory_digest
    ):
        raise ResolveConflictError(
            "The quality finding source no longer matches the frozen Resolve Context. Run the finder again before resolving it."
        )


def _direct_memory_digest(frame: ResolveTarget) -> str:
    payload = [
        {"uid": memory.uid, "content": memory.content}
        for memory in frame.source.memories
    ]
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


class ResolveProvider(Protocol):
    """The bounded completion primitive used by Resolve semantic turns."""

    def complete(
        self,
        prompt: str,
        *,
        operation: str,
        output_schema: dict[str, object] | None = None,
    ) -> str:
        """Return one complete structured semantic response."""


class ResolveProviderFactory(Protocol):
    def __call__(self) -> ResolveProvider:
        """Connect after the complete local frame and authority are frozen."""


class ResolveApplyPort(Protocol):
    """Publish the final reviewed proposal; calculation needs no Store port."""

    def apply_update_plan(
        self,
        frame: ResolveTarget,
        plan: UpdatePlan,
        *,
        unresolved_issue_uids: tuple[str, ...] = (),
        finalized_inputs: tuple[ResolveFinalizedInput, ...] = (),
    ) -> ResolveReceipt:
        """Publish one Resolve-generated exact Update plan atomically."""


class ResolveSemanticPort(Protocol):
    def analyze(
        self,
        frame: ResolveTarget,
        audit: QualityAuditSession,
        *,
        issues: tuple[AuditResolutionIssue, ...],
        provider: ResolveProvider | None = None,
    ) -> ResolveAnalysis:
        """Generate one direction per selected issue, using the complete Context."""
