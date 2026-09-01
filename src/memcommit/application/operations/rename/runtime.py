"""MemoryStore implementation of Context namespace Rename."""

from __future__ import annotations

from memcommit.application.capabilities.operand_resolution import (
    freeze_local_context_operand_candidates,
    resolve_existing_context_operand,
)
from memcommit.application.capabilities.context_locator import resolve_context_locator
from memcommit.application.capabilities.durable_uid_resolution import (
    is_unresolved_uid_selector,
)
from memcommit.application.operations.rename.application import (
    RenameBinding,
    RenamePlan,
    RenameRequest,
    RenameResult,
    apply_rename,
    plan_rename,
)
from memcommit.core.context_targeting.naming import validate_portable_context_name
from memcommit.persistence.store import MemoryStore
from memcommit.persistence.store.context_memory.models import ContextRenamePlan


class MemoryStoreRenamePort:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def freeze(self, request: RenameRequest) -> RenamePlan:
        if not is_unresolved_uid_selector(request.old_locator):
            lexical_old_name = resolve_context_locator(
                request.old_locator,
                current=request.current_context_name,
            )
            try:
                validate_portable_context_name(lexical_old_name)
            except ValueError as error:
                raise ValueError(
                    "General Context rename requires a portable existing Context "
                    "name; use 'mem profile migrate-context' for a nonportable "
                    "legacy source."
                ) from error
        old_name = resolve_existing_context_operand(
            freeze_local_context_operand_candidates(self._store),
            request.old_locator,
            current=request.current_context_name,
        ).name
        validate_portable_context_name(old_name)
        token = self._store.plan_context_rename(old_name, request.new_name)
        return RenamePlan(
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
            reference_count=token.reference_count,
            checkpoint_reference_count=token.checkpoint_reference_count,
            translation_artifact_count=token.translation_artifact_count,
            meld_session_count=token.meld_session_count,
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
            old_name=plan.old_name,
            new_name=plan.new_name,
            renamed_context_count=result.renamed_context_count,
            changed_owner_count=result.changed_owner_count,
            reference_count=result.reference_count,
            checkpoint_reference_count=result.checkpoint_reference_count,
            translation_artifact_count=result.translation_artifact_count,
            meld_session_count=result.meld_session_count,
            current_context=result.current_context,
        )


def prepare_rename(store: MemoryStore, request: RenameRequest) -> RenamePlan:
    return plan_rename(request, port=MemoryStoreRenamePort(store))


def execute_rename(store: MemoryStore, plan: RenamePlan) -> RenameResult:
    return apply_rename(plan, port=MemoryStoreRenamePort(store))


__all__ = ["MemoryStoreRenamePort", "execute_rename", "prepare_rename"]
