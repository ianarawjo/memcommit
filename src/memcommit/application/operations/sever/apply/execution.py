"""Production Sever Apply port with authority checks around save-mode execution."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.context_access.access import (
    revalidate_granted_context_binding,
)
from memcommit.application.operations.profile.config import ProfileRegistry
from memcommit.application.operations.profile.model import (
    ProfileError,
    authority_grant_snapshot_lock,
)
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
from memcommit.application.operations.sever.inputs import capture_sever_binding
from memcommit.application.operations.sever.model import (
    SeverContextBinding,
    SeverSession,
)
from memcommit.application.operations.update.model import (
    GrantedUpdateTarget,
)
from memcommit.persistence.store import (
    MemoryStore,
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

    def _materialize_frozen(self, session: SeverSession) -> SeverSession:
        if session.save_mode == "SELF_SAVE":
            return materialize_self_save(self.store, session)
        return materialize_other_save(self.store, session)

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
        granted_bindings = tuple(
            (label, binding)
            for label, binding in (
                ("Source", session.source),
                ("Criteria", session.criteria),
            )
            if binding.granted is not None
        )
        if not granted_bindings:
            return self._materialize_frozen(session)

        # Freeze the grant registry across both validation passes and output
        # creation. The second pass makes the Result's commit point observe
        # the exact authority content captured by the reviewed session.
        with authority_grant_snapshot_lock() as registry:
            for label, binding in granted_bindings:
                self._revalidate_granted_binding(label, binding, registry)
            applied = self._materialize_frozen(session)
            try:
                for label, binding in granted_bindings:
                    self._revalidate_granted_binding(label, binding, registry)
            except Exception:
                self.rollback_materialization(applied)
                raise
            return applied

    def _revalidate_granted_binding(
        self,
        label: str,
        binding: SeverContextBinding,
        registry: ProfileRegistry,
    ) -> None:
        if binding.granted is None:
            raise SeverApplicationError(f"The Sever {label} is not a granted input.")
        frozen = GrantedUpdateTarget.from_dict(binding.granted)
        try:
            access = revalidate_granted_context_binding(
                frozen,
                required_permission="READ",
                registry=registry,
                active_store=self.store,
            )
            current = capture_sever_binding(
                access,
                include_descendants=binding.include_descendants,
                registry=registry,
            )
        except (FileNotFoundError, ProfileError, ValueError) as error:
            raise SeverApplicationError(
                f"The granted Sever {label} is no longer authorized for Apply."
            ) from error
        if current != binding:
            raise SeverApplicationError(
                f"The granted Sever {label} changed after review. Re-run Sever."
            )
