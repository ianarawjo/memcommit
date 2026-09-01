"""MemoryStore-backed preparation for candidate-based Meld execution."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from memcommit.application.context_access.access import ContextAccess, resolve_context_access
from memcommit.application.operations.meld.model import (
    INLINE_MELD_CONTEXT_NAME,
    MELD_CANDIDATE_SCHEMA_VERSION,
    MeldFrame,
    MeldSession,
    MeldTarget,
    meld_canonical_digest,
)
from memcommit.application.operations.meld.preparation import (
    MeldRestartError,
    MeldRestartPort,
    MeldRestartRequest,
    MeldRestartResult,
    MeldStartError,
    MeldStartOrigin,
    MeldStartPort,
    MeldStartRequest,
    MeldStartResult,
    run_meld_restart,
    run_meld_start,
)
from memcommit.application.operations.meld.resolution import analyze_meld_candidate
from memcommit.core.context import AutoCheckpoint, Context, Memory
from memcommit.persistence.operations.audit import JsonAuditRecordRepository
from memcommit.persistence.store import ConcurrentContextUpdateError, MemoryStore

from .source_access import load_meld_source


@dataclass(frozen=True)
class PreparedMeldExecution:
    """Frozen Source/Target frame before any semantic provider is connected."""

    request: MeldStartRequest | MeldRestartRequest
    store: MemoryStore
    current_name: str | None
    left_access: ContextAccess | None
    right_access: ContextAccess
    left: Context
    right: Context
    target: Context
    expected_session_digest: str | None
    create_target: bool
    provider_required: bool = True


def _inline_context(content: str) -> Context:
    digest = uuid.uuid5(uuid.NAMESPACE_URL, f"memcommit:meld:inline:{content}")
    context = Context(
        uid=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{digest}:context")),
        name=INLINE_MELD_CONTEXT_NAME,
    )
    context.add(
        Memory(
            str(uuid.uuid5(uuid.NAMESPACE_URL, f"{digest}:memory")),
            content,
        )
    )
    return context


def _prepare_initial_meld(
    request: MeldStartRequest | MeldRestartRequest,
    *,
    store: MemoryStore,
    expected_session_digest: str | None,
    create_target: bool,
    error_type: type[RuntimeError],
) -> PreparedMeldExecution:
    """Freeze direct local Sources and the exact Target without semantic work."""

    if request.left_descendants or request.right_descendants:
        raise error_type(
            "Candidate-based Meld currently requires direct Context Sources; "
            "descendant placement needs an owner-preserving post-image contract."
        )
    current_name = store.current_context_name()
    inline = request.incoming_text is not None
    left_access = (
        None
        if inline
        else resolve_context_access(
            store,
            request.left_name,
            current_name=current_name,
            required_permission="READ",
        )
    )
    right_access = resolve_context_access(
        store,
        request.right_name,
        current_name=current_name,
        required_permission="READ",
    )
    if right_access.is_granted or (
        left_access is not None and left_access.is_granted
    ):
        raise error_type(
            "Candidate-based Meld currently requires local Sources and Target."
        )
    right = load_meld_source(right_access, project=False)
    if request.incoming_text is not None:
        left = _inline_context(request.incoming_text)
    else:
        assert left_access is not None
        left = load_meld_source(left_access, project=False)
    if request.mode == "DIRECTIONAL":
        target = right
    elif create_target:
        store.assert_context_creatable(request.target_name)
        target = Context(uid=str(uuid.uuid4()), name=request.target_name)
    else:
        target_access = resolve_context_access(
            store,
            request.target_name,
            current_name=current_name,
            required_permission="READ",
        )
        if target_access.is_granted:
            raise error_type("Symmetric Meld requires a local Result Context.")
        target = store.load_direct(request.target_name)
        if tuple(target.iter_items()):
            raise error_type("Symmetric Meld Result must remain empty.")

    prior = store.load_meld_session(target.uid)
    if expected_session_digest is None:
        if prior is not None:
            raise error_type("The Meld target already owns a saved session.")
    else:
        if prior is None:
            raise ConcurrentContextUpdateError(
                "The Meld session disappeared before restart."
            )
        if meld_canonical_digest(prior.to_dict()) != expected_session_digest:
            raise ConcurrentContextUpdateError(
                "The Meld session changed before restart."
            )
    return PreparedMeldExecution(
        request=request,
        store=store,
        current_name=current_name,
        left_access=left_access,
        right_access=right_access,
        left=left,
        right=right,
        target=target,
        expected_session_digest=expected_session_digest,
        create_target=create_target,
    )


def _candidate_session(prepared: PreparedMeldExecution) -> MeldSession:
    request = prepared.request
    if request.mode == "SYMMETRIC":
        frames = (
            MeldFrame.from_context(prepared.left, role="PEER"),
            MeldFrame.from_context(prepared.right, role="PEER"),
        )
        target = MeldTarget.from_context(prepared.target)
    else:
        frames = (
            MeldFrame.from_context(
                prepared.left,
                role="INCOMING",
                owner_aware=True,
                memory_selector=request.incoming_memory,
            ),
            MeldFrame.from_context(
                prepared.right,
                role="BASELINE",
                owner_aware=True,
                memory_selector=request.baseline_memory,
            ),
        )
        target = MeldTarget.from_baseline_context(
            prepared.target,
            context_digest=frames[1].context_digest,
        )
    return MeldSession(
        uid=str(uuid.uuid4()),
        mode=request.mode,
        frames=frames,
        target=target,
        schema_version=MELD_CANDIDATE_SCHEMA_VERSION,
    )


def _execute_prepared_initial_meld(
    prepared: PreparedMeldExecution,
    *,
    provider_factory,
    error_type: type[RuntimeError],
) -> tuple[MeldSession, MeldStartOrigin]:
    """Audit the lossless candidate and publish only its complete review."""

    del error_type
    session = _candidate_session(prepared)
    analyze_meld_candidate(
        session,
        audit_repository=JsonAuditRecordRepository(prepared.store),
        provider_factory=provider_factory,
    )
    if prepared.create_target:
        prepared.store.create_meld_target_with_session(
            prepared.target,
            session,
            AutoCheckpoint(
                command="meld",
                args={
                    "left": prepared.request.left_name,
                    "right": prepared.request.right_name,
                    "to": prepared.request.target_name,
                    "contract": "AUDIT_RESOLVE_UPDATE",
                },
                description=(
                    f"Initialized Meld candidate '{prepared.request.target_name}' "
                    "from two frozen Sources"
                ),
            ),
        )
    else:
        prepared.store.save_meld_session(
            session,
            expected_session_digest=prepared.expected_session_digest,
        )
    return session, "AUDIT_RESOLVE_UPDATE"


def _execute_initial_meld(
    request: MeldStartRequest | MeldRestartRequest,
    *,
    store: MemoryStore,
    provider_factory,
    expected_session_digest: str | None,
    create_target: bool,
    error_type: type[RuntimeError],
) -> tuple[MeldSession, MeldStartOrigin]:
    prepared = _prepare_initial_meld(
        request,
        store=store,
        expected_session_digest=expected_session_digest,
        create_target=create_target,
        error_type=error_type,
    )
    return _execute_prepared_initial_meld(
        prepared,
        provider_factory=provider_factory,
        error_type=error_type,
    )


@dataclass
class MemoryStoreMeldStartPort(MeldStartPort):
    store: MemoryStore
    prepared: PreparedMeldExecution | None = None

    def start(self, request: MeldStartRequest, *, provider_factory) -> MeldStartResult:
        if self.prepared is not None:
            if self.prepared.request != request or self.prepared.store is not self.store:
                raise MeldStartError("Prepared Meld Start does not match its request.")
            session, origin = _execute_prepared_initial_meld(
                self.prepared,
                provider_factory=provider_factory,
                error_type=MeldStartError,
            )
        else:
            session, origin = _execute_initial_meld(
                request,
                store=self.store,
                provider_factory=provider_factory,
                expected_session_digest=None,
                create_target=request.create_target,
                error_type=MeldStartError,
            )
        return MeldStartResult(
            session=session,
            origin=origin,
            created_target=request.create_target,
        )


def execute_meld_start(
    request: MeldStartRequest,
    *,
    store: MemoryStore,
    provider_factory,
    prepared: PreparedMeldExecution | None = None,
) -> MeldStartResult:
    return run_meld_start(
        request,
        port=MemoryStoreMeldStartPort(store, prepared=prepared),
        provider_factory=provider_factory,
    )


def prepare_meld_start(
    request: MeldStartRequest,
    *,
    store: MemoryStore,
) -> PreparedMeldExecution:
    return _prepare_initial_meld(
        request,
        store=store,
        expected_session_digest=None,
        create_target=request.create_target,
        error_type=MeldStartError,
    )


@dataclass
class MemoryStoreMeldRestartPort(MeldRestartPort):
    store: MemoryStore
    prepared: PreparedMeldExecution | None = None

    def restart(
        self,
        request: MeldRestartRequest,
        *,
        provider_factory,
    ) -> MeldRestartResult:
        if self.prepared is not None:
            if self.prepared.request != request or self.prepared.store is not self.store:
                raise MeldRestartError(
                    "Prepared Meld Restart does not match its request."
                )
            session, origin = _execute_prepared_initial_meld(
                self.prepared,
                provider_factory=provider_factory,
                error_type=MeldRestartError,
            )
        else:
            session, origin = _execute_initial_meld(
                request,
                store=self.store,
                provider_factory=provider_factory,
                expected_session_digest=request.expected_version,
                create_target=False,
                error_type=MeldRestartError,
            )
        return MeldRestartResult(session=session, origin=origin)


def execute_meld_restart(
    request: MeldRestartRequest,
    *,
    store: MemoryStore,
    provider_factory,
    prepared: PreparedMeldExecution | None = None,
) -> MeldRestartResult:
    return run_meld_restart(
        request,
        port=MemoryStoreMeldRestartPort(store, prepared=prepared),
        provider_factory=provider_factory,
    )


def prepare_meld_restart(
    request: MeldRestartRequest,
    *,
    store: MemoryStore,
) -> PreparedMeldExecution:
    return _prepare_initial_meld(
        request,
        store=store,
        expected_session_digest=request.expected_version,
        create_target=False,
        error_type=MeldRestartError,
    )


__all__ = [
    "MemoryStoreMeldRestartPort",
    "MemoryStoreMeldStartPort",
    "PreparedMeldExecution",
    "execute_meld_restart",
    "execute_meld_start",
    "prepare_meld_restart",
    "prepare_meld_start",
]
