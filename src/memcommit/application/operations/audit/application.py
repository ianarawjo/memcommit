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
    QualityAuditFit,
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
    FrozenContextConformance,
    freeze_context_conformance,
)
from memcommit.application.operations.fit.judgment import (
    FIT_JUDGMENT_OPERATION,
    FitProposition,
    judge_fit,
)
from memcommit.core.context import Context, Memory
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
    fit: QualityAuditFit | None = None,
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
        fit=fit,
        conformance=conformance,
    )
    return QualityAuditSession.from_dict(session.to_dict())


def record_quality_audit(
    repository: AuditRecordRepository,
    session: QualityAuditSession,
) -> None:
    """Publish one fully validated completed Audit through its persistence port."""

    repository.create(QualityAuditSession.from_dict(session.to_dict()))


def _conformance_matches(
    session: QualityAuditSession,
    frozen_rules: FrozenContextConformance | None,
) -> bool:
    """Match an explicitly requested Rules frame without weakening Audit reuse."""

    if frozen_rules is None:
        # With no newly supplied Rules operand, the newest exact-source Audit is
        # reusable as recorded, including its optional Conformance check.
        return True
    conformance = session.conformance
    if conformance is None:
        return False
    return (
        conformance.rules_label == frozen_rules.rules_name
        and tuple((rule.uid, rule.content) for rule in conformance.rules)
        == tuple((rule.uid, rule.content) for rule in frozen_rules.rules)
    )


def find_current_quality_audit(
    repository: AuditRecordRepository,
    ctx: Context,
    *,
    conformance_rules: Context | None = None,
) -> QualityAuditSession | None:
    """Return the newest Audit over the exact current direct-Memory frame."""

    source = QualityAuditSource.from_context(ctx)
    frozen_rules = (
        None
        if conformance_rules is None
        else freeze_context_conformance(source.context(), conformance_rules)
    )
    matches = tuple(
        session
        for session in repository.list()
        if session.source.context_uid == source.context_uid
        and session.source.context_digest == source.context_digest
        # Schema-v1 records remain reviewable, but a multi-Memory Audit without
        # its whole-set Fit section is not reusable for current Resolve/Meld.
        and (len(source.memories) < 2 or session.fit is not None)
        and _conformance_matches(session, frozen_rules)
    )
    if not matches:
        return None
    return max(matches, key=lambda session: (session.created_at, session.uid))


def get_or_run_quality_audit(
    ctx: Context,
    provider_factory: Callable[[], FindingsProvider],
    repository: AuditRecordRepository,
    *,
    conformance_rules: Context | None = None,
    on_check: Callable[[QualityAuditKind, int, int], None] | None = None,
    on_fit: Callable[[], None] | None = None,
    on_conformance: Callable[[], None] | None = None,
) -> QualityAuditSession:
    """Reuse one exact completed Audit or atomically publish a fresh result."""

    current = find_current_quality_audit(
        repository,
        ctx,
        conformance_rules=conformance_rules,
    )
    if current is not None:
        return current
    session = run_quality_audit(
        ctx,
        provider_factory,
        conformance_rules=conformance_rules,
        on_check=on_check,
        on_fit=on_fit,
        on_conformance=on_conformance,
    )
    record_quality_audit(repository, session)
    return session


def audit_conformance_rules_context(
    session: QualityAuditSession,
) -> Context | None:
    """Reconstruct the exact frozen Rules frame for a post-image Audit."""

    conformance = session.conformance
    if conformance is None:
        return None
    rules = Context(
        uid=str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"memcommit:audit-rules:{conformance.digest}",
            )
        ),
        name=conformance.rules_label,
    )
    for rule in conformance.rules:
        rules.add(Memory(rule.uid, rule.content))
    return rules


def run_quality_audit(
    ctx: Context,
    provider_factory: Callable[[], FindingsProvider],
    *,
    conformance_rules: Context | None = None,
    on_check: Callable[[QualityAuditKind, int, int], None] | None = None,
    on_fit: Callable[[], None] | None = None,
    on_conformance: Callable[[], None] | None = None,
) -> QualityAuditSession:
    """Run every configured Audit check over one frozen direct Context frame."""

    source = QualityAuditSource.from_context(ctx)
    frozen = source.context()
    # Validate the optional Rules frame before any provider connection so an
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

    fit = None
    frozen_memories = tuple(
        item for item in frozen.iter_items() if isinstance(item, Memory)
    )
    if len(frozen_memories) >= 2:
        if on_fit is not None:
            on_fit()
        capture = _CapturingProviderFactory(provider_factory)
        aliases = tuple(
            f"m{index:06d}" for index in range(1, len(frozen_memories) + 1)
        )
        fit_analysis = judge_fit(
            tuple(
                FitProposition(alias, memory.content, role="MEMORY")
                for alias, memory in zip(aliases, frozen_memories, strict=True)
            ),
            provider=capture(),
        )
        material_aliases = set(fit_analysis.assessment.material_proposition_ids)
        fit = QualityAuditFit(
            uid=fit_analysis.uid,
            created_at=fit_analysis.created_at,
            verdict=fit_analysis.assessment.verdict,
            reason=fit_analysis.assessment.reason,
            overview=fit_analysis.overview,
            considered_memory_uids=tuple(memory.uid for memory in frozen_memories),
            material_memory_uids=tuple(
                memory.uid
                for alias, memory in zip(aliases, frozen_memories, strict=True)
                if alias in material_aliases
            ),
            consistent_reading=fit_analysis.assessment.consistent_reading,
            inconsistent_reading=fit_analysis.assessment.inconsistent_reading,
            provenance=capture.provenance(FIT_JUDGMENT_OPERATION),
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
        fit=fit,
        conformance=conformance,
    )


__all__ = [
    "audit_conformance_rules_context",
    "create_quality_audit",
    "find_current_quality_audit",
    "get_or_run_quality_audit",
    "record_quality_audit",
    "run_quality_audit",
]
