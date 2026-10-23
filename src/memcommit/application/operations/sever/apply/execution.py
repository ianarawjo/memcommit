"""Production Sever Apply port with authority checks around save-mode execution."""

from __future__ import annotations


from dataclasses import dataclass

from memcommit.application.operations.sever.application import (
    SeverApplicationError,
)
from memcommit.application.operations.sever.apply.other_save import (
    materialize_other_save,
    recover_other_save,
    rollback_other_save,
)
from memcommit.application.operations.sever.apply.self_save import (
    materialize_self_save,
    recover_self_save,
    rollback_self_save,
)
from memcommit.application.operations.sever.model import (
    SeverSession,
)
from memcommit.persistence.store import (
    MemoryStore,
    ConcurrentContextUpdateError,
)


@dataclass
class MemoryStoreSeverOutputPort:
    """Keep authority validation around the complete save-mode transaction."""

    store: MemoryStore

    def recover_materialization(self, session: SeverSession) -> SeverSession | None:
        if not self.store.context_exists(session.output_name):
            return None
        if session.save_mode == "SELF_SAVE":
            return recover_self_save(self.store, session)
        return recover_other_save(self.store, session)

    def _materialize_frozen(
        self, session: SeverSession, *, context_catalog: tuple[str, ...]
    ) -> SeverSession:
        if session.save_mode == "SELF_SAVE":
            return materialize_self_save(
                self.store, session, expected_context_catalog=context_catalog
            )
        return materialize_other_save(
            self.store, session, expected_context_catalog=context_catalog
        )

    def rollback_materialization(self, applied: SeverSession) -> None:
        if applied.state != "APPLIED" or applied.application is None:
            raise SeverApplicationError(
                "Only an applied Sever receipt can roll back its Result."
            )
        if applied.save_mode == "SELF_SAVE":
            rollback_self_save(self.store, applied)
        else:
            rollback_other_save(self.store, applied)

    def materialize(self, session: SeverSession) -> SeverSession:
        from memcommit.application.context_access.access import ContextAccess
        from memcommit.application.operations.sever.inputs import capture_sever_binding

        # Capture membership before re-reading either input. Store publication
        # checks this same catalog and every frozen content digest under locks.
        context_catalog = tuple(self.store.list_context_names())
        for binding in (session.source, session.criteria):
            current = capture_sever_binding(
                ContextAccess(self.store, binding.root_name, binding.root_name),
                include_descendants=binding.include_descendants,
            )
            if current != binding:
                raise ConcurrentContextUpdateError(
                    "Sever input changed before the result could be saved."
                )
        return self._materialize_frozen(session, context_catalog=context_catalog)
