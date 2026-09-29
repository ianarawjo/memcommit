"""Terminal-independent orchestration for the requested quality Audit checks."""

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
    QUALITY_AUDIT_OPERATIONS,
    QUALITY_AUDIT_RULESETS,
    AuditCheckKind,
    QualityAuditCheck,
    QualityAuditError,
    QualityAuditKind,
    QualityAuditProvenance,
    QualityAuditReport,
    QualityAuditSession,
    QualityAuditSource,
)
from memcommit.application.operations.audit.repository import AuditRecordRepository
from memcommit.application.operations.duplicates.find_duplicates.application import (
    analyze_exact_duplicates,
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
    requested_checks: tuple[AuditCheckKind, ...],
    uid: str | None = None,
    created_at: str | None = None,
) -> QualityAuditSession:
    """Create and fully validate one completed Audit snapshot."""

    source = QualityAuditSource.from_context(ctx)
    return QualityAuditSession(
        uid=uid or str(uuid.uuid4()),
        created_at=created_at
        or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        source=source,
        checks=checks,
        requested_checks=requested_checks,
    )


def record_quality_audit(
    repository: AuditRecordRepository,
    session: QualityAuditSession,
) -> None:
    """Publish one fully validated completed Audit through its persistence port."""

    repository.create(session)


def standard_quality_audit_checks() -> frozenset[AuditCheckKind]:
    """Build the standard issue-finding selection for Audit callers."""
    return frozenset(
        {
            AuditCheckKind.DUN,
            AuditCheckKind.AMBIGUITIES,
            AuditCheckKind.CONFLICTS,
        }
    )


def _select_checks(
    checks: frozenset[AuditCheckKind],
) -> tuple[AuditCheckKind, ...]:
    """Validate the entire request before connecting to any provider."""

    if not isinstance(checks, frozenset) or any(
        not isinstance(kind, AuditCheckKind) for kind in checks
    ):
        raise QualityAuditError(
            "Audit checks must be a frozenset of AuditCheckKind values."
        )
    if not checks:
        raise QualityAuditError("Audit must request at least one check.")
    return tuple(kind for kind in AuditCheckKind if kind in checks)


def find_current_quality_audit(
    repository: AuditRecordRepository,
    ctx: Context,
    *,
    checks: frozenset[AuditCheckKind],
) -> QualityAuditSession | None:
    """Return the newest Audit over the exact current direct-Memory frame."""

    source = QualityAuditSource.from_context(ctx)
    selected = _select_checks(checks)
    matches = tuple(
        session
        for session in repository.list()
        if session.source == source
        # Reusing a superset would send unrequested findings into Resolve.
        and session.requested_checks == selected
    )
    if not matches:
        return None
    return max(matches, key=lambda session: (session.created_at, session.uid))


def get_or_run_quality_audit(
    ctx: Context,
    provider_factory: Callable[[], FindingsProvider],
    repository: AuditRecordRepository,
    *,
    checks: frozenset[AuditCheckKind],
    on_check: Callable[[QualityAuditKind, int, int], None] | None = None,
) -> QualityAuditSession:
    """Reuse one exact completed Audit or atomically publish a fresh result."""

    current = find_current_quality_audit(
        repository,
        ctx,
        checks=checks,
    )
    if current is not None:
        return current
    session = run_quality_audit(
        ctx,
        provider_factory,
        checks=checks,
        on_check=on_check,
    )
    record_quality_audit(repository, session)
    return session


def run_quality_audit(
    ctx: Context,
    provider_factory: Callable[[], FindingsProvider],
    *,
    checks: frozenset[AuditCheckKind],
    on_check: Callable[[QualityAuditKind, int, int], None] | None = None,
) -> QualityAuditSession:
    """Run exactly the explicitly selected checks over one frozen Source."""

    source = QualityAuditSource.from_context(ctx)
    selected = _select_checks(checks)
    frozen = source.context()
    operations: tuple[
        tuple[
            QualityAuditKind,
            Callable[[Context, Callable[[], FindingsProvider]], QualityAuditReport],
        ],
        ...,
    ] = (
        ("dup", lambda context, _provider: analyze_exact_duplicates(context)),
        ("dun", analyze_memory_redundancies),
        ("ambiguities", analyze_memory_ambiguities),
        ("conflicts", analyze_memory_conflicts),
    )
    operations = tuple(
        (kind, finder)
        for kind, finder in operations
        if AuditCheckKind(kind) in selected
    )
    results: list[QualityAuditCheck] = []
    exact_groups = None
    for index, (kind, finder) in enumerate(operations, start=1):
        if on_check is not None:
            on_check(kind, index, len(operations))
        capture = _CapturingProviderFactory(provider_factory)
        if kind == "dun":
            report = analyze_memory_redundancies(
                frozen, capture, exact_groups=exact_groups
            )
        else:
            report = finder(frozen, capture)
        if kind == "dup":
            exact_groups = report.groups
        results.append(
            QualityAuditCheck(
                kind=kind,
                ruleset_version=QUALITY_AUDIT_RULESETS[kind],
                report=report,
                provenance=capture.provenance(QUALITY_AUDIT_OPERATIONS[kind]),
            )
        )

    return create_quality_audit(
        frozen,
        tuple(results),
        requested_checks=selected,
    )


__all__ = [
    "create_quality_audit",
    "find_current_quality_audit",
    "get_or_run_quality_audit",
    "record_quality_audit",
    "run_quality_audit",
    "standard_quality_audit_checks",
]


def audit_post_image(
    previous: QualityAuditSession,
    context: Context,
    provider_factory: Callable[[], FindingsProvider],
) -> QualityAuditSession:
    """Recheck the selected policy without silently widening to default checks."""
    selected = frozenset(previous.requested_checks)
    return run_quality_audit(
        context,
        provider_factory,
        checks=selected,
    )
