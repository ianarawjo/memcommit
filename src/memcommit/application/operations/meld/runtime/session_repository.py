"""MemoryStore-backed persistence for durable Meld proposal sessions."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.operations.meld.apply import MeldApplicationError
from memcommit.application.operations.meld.model import (
    MeldSession,
    materialize_preservation_assessment,
    meld_canonical_digest,
)
from memcommit.application.operations.meld.proposal_iteration import (
    MeldDestinationPort,
    MeldDestinationRequest,
    MeldPreservationPort,
    MeldSessionRepository,
    MeldSessionSnapshot,
    run_meld_destination_change,
    run_meld_initial_preservation,
    run_meld_preservation,
    run_meld_session_defer,
    run_meld_session_open,
)
from memcommit.core.context_targeting.naming import validate_portable_context_name
from memcommit.persistence.store import MemoryStore

from .source_access import (
    assert_meld_source_bindings,
    assert_unapplied_meld_target,
    load_bound_meld_contexts,
)


@dataclass
class MemoryStoreMeldSessionRepository(MeldSessionRepository):
    """Target-scoped Meld persistence with opaque canonical-digest CAS tokens."""

    store: MemoryStore

    @staticmethod
    def _snapshot(session: MeldSession) -> MeldSessionSnapshot:
        return MeldSessionSnapshot(
            session=session,
            version_token=meld_canonical_digest(session.to_dict()),
        )

    def load(self, target_context_uid: str) -> MeldSessionSnapshot:
        session = self.store.load_meld_session(target_context_uid)
        if session is None:
            raise FileNotFoundError(
                f"No saved Meld session for target {target_context_uid!r}."
            )
        return self._snapshot(session)

    def replace(
        self,
        session: MeldSession,
        *,
        expected_version: str,
    ) -> MeldSessionSnapshot:
        self.store.save_meld_session(
            session,
            expected_session_digest=expected_version,
        )
        return self._snapshot(session)


@dataclass
class MemoryStoreMeldPreservationPort(MeldPreservationPort):
    """Revalidate and publish one provider-free symmetric preserve-all turn."""

    store: MemoryStore

    def materialize(
        self,
        snapshot: MeldSessionSnapshot,
        session: MeldSession,
    ) -> MeldSessionSnapshot:
        assessment = materialize_preservation_assessment(session)
        left, right, target = load_bound_meld_contexts(self.store, session)
        assert_meld_source_bindings(session, left, right)
        assert_unapplied_meld_target(session, target)
        current = session.current_turn
        assert current is not None
        session.record_assessment(current.uid, assessment)
        return MemoryStoreMeldSessionRepository(self.store).replace(
            session,
            expected_version=snapshot.version_token,
        )


@dataclass
class MemoryStoreMeldDestinationPort(MeldDestinationPort):
    """Relocate one empty symmetric Result and its target-scoped session."""

    store: MemoryStore

    def relocate(self, request: MeldDestinationRequest) -> MeldSessionSnapshot:
        destination = request.destination_name
        validate_portable_context_name(destination)
        session = request.snapshot.session
        descendants = tuple(
            name
            for name in self.store.list_context_names()
            if name.startswith(session.target.context_name + "/")
        )
        if descendants:
            raise ValueError(
                "A symmetric Meld save location with descendants cannot be moved "
                "from the review workbench."
            )
        current = MemoryStoreMeldSessionRepository(self.store).load(
            session.target.context_uid
        )
        if current.version_token != request.snapshot.version_token:
            raise MeldApplicationError(
                "The Meld session changed before its destination could move."
            )
        plan = self.store.plan_context_rename(
            session.target.context_name,
            destination,
        )
        self.store.rename_contexts(plan)
        relocated = self.store.load_meld_session(session.target.context_uid)
        if relocated is None or relocated.uid != session.uid:
            raise MeldApplicationError(
                "The relocated Meld session could not be reloaded."
            )
        return MemoryStoreMeldSessionRepository._snapshot(relocated)


def execute_meld_session_open(
    target_context_uid: str,
    *,
    store: MemoryStore,
) -> MeldSessionSnapshot:
    return run_meld_session_open(
        target_context_uid,
        repository=MemoryStoreMeldSessionRepository(store),
    )


def execute_meld_session_defer(
    snapshot: MeldSessionSnapshot,
    *,
    store: MemoryStore,
) -> MeldSessionSnapshot:
    return run_meld_session_defer(
        snapshot,
        repository=MemoryStoreMeldSessionRepository(store),
    )


def execute_meld_initial_preservation(
    snapshot: MeldSessionSnapshot,
    *,
    store: MemoryStore,
) -> MeldSessionSnapshot:
    return run_meld_initial_preservation(
        snapshot,
        repository=MemoryStoreMeldSessionRepository(store),
    )


def execute_meld_preservation(
    pending,
    *,
    store: MemoryStore,
) -> MeldSessionSnapshot:
    return run_meld_preservation(
        pending,
        port=MemoryStoreMeldPreservationPort(store),
    )


def execute_meld_destination_change(
    request: MeldDestinationRequest,
    *,
    store: MemoryStore,
) -> MeldSessionSnapshot:
    return run_meld_destination_change(
        request,
        port=MemoryStoreMeldDestinationPort(store),
    )
