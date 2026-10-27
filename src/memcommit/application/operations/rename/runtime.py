"""ProfileStore implementation of Context namespace Rename."""

from __future__ import annotations


from memcommit.application.capabilities.operand_resolution import (
    freeze_local_context_operand_candidates,
    resolve_existing_context_operand,
)
from memcommit.application.operations.rename.application import (
    RenameBinding,
    RenamePlan,
    RenameRequest,
    RenameResult,
    apply_rename,
    plan_rename,
)
from memcommit.persistence.store import ProfileStore
from memcommit.persistence.store.context_memory.models import ContextRenamePlan


class MemoryStoreRenamePort:
    def __init__(self, store: ProfileStore) -> None:
        self._store = store

    def freeze(self, request: RenameRequest) -> RenamePlan:
        return self._freeze_context(request)

    def _freeze_context(self, request: RenameRequest) -> RenamePlan:
        old_name = resolve_existing_context_operand(
            freeze_local_context_operand_candidates(self._store),
            request.old_locator,
            current=request.current_context_name,
        ).name
        token = self._store.plan_context_rename(old_name, request.new_name)
        return RenamePlan(
            subject="CONTEXT_NAMESPACE",
            old_name=token.old_name,
            new_name=token.new_name,
            bindings=tuple(
                RenameBinding(
                    old_name=binding.old_name,
                    new_name=binding.new_name,
                    context_uid=binding.context_uid,
                )
                for binding in token.bindings
            ),
            changed_owner_count=len(token.changed_owner_names),
            current_before=token.current_before,
            current_after=token.current_after,
            graph_digest=token.graph_digest,
            token=token,
        )

    def apply(self, plan: RenamePlan) -> RenameResult:
        token = plan.token
        if not isinstance(token, ContextRenamePlan):
            raise TypeError("Rename plan token is invalid.")
        result = self._store.rename_contexts(token)
        return RenameResult(
            subject="CONTEXT_NAMESPACE",
            old_name=plan.old_name,
            new_name=plan.new_name,
            renamed_context_count=result.renamed_context_count,
            changed_owner_count=result.changed_owner_count,
            current_context=result.current_context,
        )


def prepare_rename(store: ProfileStore, request: RenameRequest) -> RenamePlan:
    return plan_rename(request, port=MemoryStoreRenamePort(store))


def execute_rename(store: ProfileStore, plan: RenamePlan) -> RenameResult:
    return apply_rename(plan, port=MemoryStoreRenamePort(store))


__all__ = [
    "MemoryStoreRenamePort",
    "execute_rename",
    "prepare_rename",
]
