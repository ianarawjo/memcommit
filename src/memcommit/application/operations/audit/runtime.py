"""Load one Audit input, run its checks, and publish the completed record."""

from __future__ import annotations

from collections.abc import Callable

from memcommit.application.capabilities.memory_issue_analysis.model import (
    FindingsProvider,
)
from memcommit.application.context_access.access import GrantedReadStore
from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
)
from memcommit.application.operations.audit.application import (
    record_quality_audit,
    run_quality_audit,
    standard_quality_audit_checks,
)
from memcommit.application.operations.audit.inputs import AuditRequest
from memcommit.application.operations.audit.model import (
    AuditCheckKind,
    QualityAuditSession,
)
from memcommit.application.operations.audit.repository import AuditRecordRepository
from memcommit.persistence.store import MemoryStore


def run_audit(
    request: AuditRequest,
    *,
    store: MemoryStore,
    provider_factory: Callable[[], FindingsProvider],
    repository: AuditRecordRepository,
    on_progress: Callable[[AuditCheckKind, int, int], None] | None = None,
) -> QualityAuditSession:
    """Run a fresh Audit and save it before returning to any output adapter."""

    current_name = store.current_context_name()
    access = resolve_existing_context_access(
        store,
        request.context_name,
        current_name=current_name,
        required_permission="READ",
    ).value
    source = (
        GrantedReadStore(access).load_direct(access.access_name)
        if access.is_granted
        else store.load_direct(access.context_name)
    )
    checks = request.checks
    if checks is None:
        checks = standard_quality_audit_checks()
    ordered_checks = tuple(kind for kind in AuditCheckKind if kind in checks)

    def notify(kind: AuditCheckKind) -> None:
        if on_progress is not None:
            on_progress(kind, ordered_checks.index(kind) + 1, len(ordered_checks))

    session = run_quality_audit(
        source,
        provider_factory,
        checks=checks,
        on_check=lambda kind, _step, _total: notify(AuditCheckKind(kind)),
    )
    # Persist only the complete result, before an adapter can lose its output.
    record_quality_audit(repository, session)
    return session
