"""Terminal-independent orchestration for one complete quality Audit."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from memcommit.application.capabilities.memory_issue_analysis.model import (
    FindingsProvider,
)
from memcommit.application.capabilities.memory_issue_analysis.reading_analysis import (
    analyze_memory_ambiguities,
)
from memcommit.application.capabilities.memory_issue_analysis.relation_analysis import (
    analyze_memory_conflicts,
    analyze_memory_redundancies,
)
from memcommit.application.operations.audit.model import (
    QUALITY_AUDIT_RULESETS,
    QualityAuditCheck,
    QualityAuditError,
    QualityAuditKind,
    QualityAuditProvenance,
    QualityAuditReport,
    QualityAuditSession,
    QualityAuditSource,
)
from memcommit.application.operations.audit.repository import AuditRecordRepository
from memcommit.application.operations.check_conformance.model import (
    ConformanceReport,
    check_context_conformance,
)
from memcommit.application.operations.check_conformance.runtime import (
    freeze_context_conformance,
)
from memcommit.core.context import Context
from memcommit.providers.types import CompletionRun, ProviderIdentity


class _CapturingProviderFactory:
    """Capture the exact provider run without changing a finder's call contract."""

    def __init__(self, factory: Callable[[], FindingsProvider]):
        self._factory = factory
        self.provider: FindingsProvider | None = None

    def __call__(self) -> FindingsProvider:
        if self.provider is not None:
            raise QualityAuditError("An Audit finder requested more than one provider.")
        self.provider = self._factory()
        return self.provider

    def provenance(self, operation: str) -> QualityAuditProvenance:
        if self.provider is None:
            return QualityAuditProvenance(operation=operation, provider_called=False)
        last_run = getattr(self.provider, "last_run", None)
        identity = getattr(self.provider, "identity", None)
        if isinstance(last_run, CompletionRun):
            identity = last_run.identity
        if not isinstance(identity, ProviderIdentity):
            raise QualityAuditError(
                "A durable Audit requires provider and model provenance."
            )
        if last_run is not None and (
            not isinstance(last_run, CompletionRun) or last_run.operation != operation
        ):
            raise QualityAuditError(
                "Audit provider provenance does not match its finder."
            )
        return QualityAuditProvenance(
            operation=operation,
            provider_called=True,
            identity=identity,
            upstream_model=(
                last_run.upstream_model if isinstance(last_run, CompletionRun) else None
            ),
            upstream_provider=(
                last_run.upstream_provider
                if isinstance(last_run, CompletionRun)
                else None
            ),
        )


def create_quality_audit(
    ctx: Context,
    checks: tuple[QualityAuditCheck, ...],
    *,
    conformance: ConformanceReport | None = None,
    uid: str | None = None,
    created_at: str | None = None,
) -> QualityAuditSession:
    """Create and fully validate one completed Audit snapshot."""

    source = QualityAuditSource.from_context(ctx)
    session = QualityAuditSession(
        uid=uid or str(uuid.uuid4()),
        created_at=created_at
        or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        source=source,
        checks=checks,
        conformance=conformance,
    )
    return QualityAuditSession.from_dict(session.to_dict())


def record_quality_audit(
    repository: AuditRecordRepository,
    session: QualityAuditSession,
) -> None:
    """Publish one fully validated completed Audit through its persistence port."""

    repository.create(QualityAuditSession.from_dict(session.to_dict()))


def run_quality_audit(
    ctx: Context,
    provider_factory: Callable[[], FindingsProvider],
    *,
    conformance_rules: Context | None = None,
    on_check: Callable[[QualityAuditKind, int, int], None] | None = None,
    on_conformance: Callable[[], None] | None = None,
) -> QualityAuditSession:
    """Run every configured Audit check over one frozen direct Context frame."""

    source = QualityAuditSource.from_context(ctx)
    frozen = source.context()
    # Validate the optional fourth frame before any provider connection so an
    # invalid Rules Context cannot leave an expensive partial Audit in flight.
    frozen_conformance = (
        None
        if conformance_rules is None
        else freeze_context_conformance(frozen, conformance_rules)
    )
    operations: tuple[
        tuple[
            QualityAuditKind,
            Callable[[Context, Callable[[], FindingsProvider]], QualityAuditReport],
        ],
        ...,
    ] = (
        ("duplicates", analyze_memory_redundancies),
        ("ambiguities", analyze_memory_ambiguities),
        ("conflicts", analyze_memory_conflicts),
    )
    checks: list[QualityAuditCheck] = []
    for index, (kind, finder) in enumerate(operations, start=1):
        if on_check is not None:
            on_check(kind, index, len(operations))
        capture = _CapturingProviderFactory(provider_factory)
        report = finder(frozen, capture)
        checks.append(
            QualityAuditCheck(
                kind=kind,
                ruleset_version=QUALITY_AUDIT_RULESETS[kind],
                report=report,
                provenance=capture.provenance(f"find_{kind}"),
            )
        )

    conformance = None
    if frozen_conformance is not None:
        if on_conformance is not None:
            on_conformance()
        conformance = check_context_conformance(
            source_label=frozen_conformance.target_name,
            rules_label=frozen_conformance.rules_name,
            rules=frozen_conformance.rules,
            subjects=frozen_conformance.subjects,
            provider=provider_factory(),
        )
    return create_quality_audit(
        frozen,
        tuple(checks),
        conformance=conformance,
    )


__all__ = ["create_quality_audit", "record_quality_audit", "run_quality_audit"]
