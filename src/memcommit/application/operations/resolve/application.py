"""Freeze one Resolve input, acquire its Audit, and derive issue directions."""

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
    FrozenResolveFrame,
    ResolveAnalysis,
    ResolveConflictError,
    ResolveRequest,
    ResolveReceipt,
)
from . import preparation
from .review_policy import remaining_review_issues, select_round_issues

if TYPE_CHECKING:
    from .decisions import ResolveFinalizedInput
    from .issue_review import IssueReviewRound
    from memcommit.application.operations.update.model import UpdatePlan
    from memcommit.core.context import Context

# Entry points share this scope; Audit and explicit application callers stay selective.
RESOLVE_CHECKS = frozenset({AuditCheckKind.CONFLICTS})


def run_resolve(
    request: ResolveRequest,
    *,
    checks: frozenset[AuditCheckKind],
    frame_port: ResolveFramePort,
    semantic_port: ResolveSemanticPort,
    audit_repository: AuditRecordRepository,
    audit_provider_factory: ResolveProviderFactory,
    direction_provider_factory: ResolveProviderFactory,
    expected_revision: str | None = None,
) -> ResolveAnalysis:
    """Acquire one exact Audit, then derive directions without applying them."""

    frame = frame_port.freeze(request)
    _require_source_precondition(frame)
    if expected_revision is not None and expected_revision != frame.revision:
        raise ResolveConflictError(
            "The Resolve Context or requested capability frame changed before "
            "its decisions could be finalized."
        )
    if frame.missing_authority or not frame.allowed_effects:
        missing = frame.missing_authority or tuple(frame.denied_effects)
        return ResolveAnalysis(
            frame=frame,
            status="NEEDS_AUTHORITY",
            question=(
                "Grant authority is missing: " + ", ".join(missing)
                if missing
                else "No requested Resolve mutation effect is authorized."
            ),
        )
    target = frame_port.load_target(frame)
    audit = preparation.audit_resolve_context(
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
    # No report is published from a stale semantic turn. Apply performs the
    # same check again under the mutation and Grant locks.
    frame_port.revalidate(frame)
    return analysis


def analyze_resolve_audit(
    frame: FrozenResolveFrame,
    audit: QualityAuditSession,
    *,
    semantic_port: ResolveSemanticPort,
    direction_provider_factory: ResolveProviderFactory,
    rounds: tuple[IssueReviewRound, ...] = (),
) -> ResolveAnalysis:
    """Derive decisions from an already acquired Audit; never apply them."""

    # Deterministic item directions need no provider connection.
    class LazyDirectionProvider:
        def complete(self, *args, **kwargs):
            return direction_provider_factory().complete(*args, **kwargs)

    provider = LazyDirectionProvider()
    issues = select_round_issues(
        remaining_review_issues(audit, rounds=rounds, frame=frame)
    )
    analysis = semantic_port.analyze(frame, audit, issues=issues, provider=provider)
    return analysis


def _require_source_precondition(frame: FrozenResolveFrame) -> None:
    expected = frame.request.source_precondition
    if expected is None:
        return
    if (
        frame.source.context_uid != expected.context_uid
        or frame.display_name != expected.display_name
        or _direct_memory_digest(frame) != expected.direct_memory_digest
    ):
        # Finder reports are observations, not mutation authority. Re-freezing
        # may therefore reauthorize, but it must never retarget stale evidence.
        raise ResolveConflictError(
            "The quality finding source no longer matches the frozen Resolve "
            "Context. Run the finder again before resolving it."
        )


def _direct_memory_digest(frame: FrozenResolveFrame) -> str:
    payload = [
        {"uid": memory.uid, "content": memory.content}
        for memory in frame.source.memories
    ]
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
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


class ResolveFramePort(Protocol):
    """Freeze, revalidate, and apply one Resolve frame."""

    def freeze(self, request: ResolveRequest) -> FrozenResolveFrame:
        """Freeze direct Memories and effective effect capabilities."""

    def revalidate(self, frame: FrozenResolveFrame) -> None:
        """Fail when the Context or Grant changed during semantic execution."""

    def load_target(self, frame: FrozenResolveFrame) -> Context:
        """Return the exact detached whole Context frozen for Update planning."""

    def apply_update_plan(
        self,
        frame: FrozenResolveFrame,
        plan: UpdatePlan,
        *,
        unresolved_issue_uids: tuple[str, ...] = (),
        finalized_inputs: tuple[ResolveFinalizedInput, ...] = (),
        removed_item_uids: tuple[str, ...] = (),
    ) -> ResolveReceipt:
        """Publish one Resolve-generated exact Update plan atomically."""


class ResolveSemanticPort(Protocol):
    def analyze(
        self,
        frame: FrozenResolveFrame,
        audit: QualityAuditSession,
        *,
        issues: tuple[AuditResolutionIssue, ...],
        provider: ResolveProvider | None = None,
    ) -> ResolveAnalysis:
        """Generate one direction per selected issue, using the complete Context."""
