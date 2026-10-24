"""MemoryStore implementation of the manual Checkpoint operation."""

from __future__ import annotations

from dataclasses import dataclass
import uuid

from memcommit.application.capabilities.operand_resolution import (
    freeze_local_context_operand_candidates,
    resolve_existing_context_operand,
)
from memcommit.application.operations.checkpoint.application import (
    CheckpointMemberPlan,
    CheckpointPlan,
    CheckpointRequest,
    CheckpointResult,
    apply_checkpoint,
    plan_checkpoint,
)
from memcommit.models.context import Context
from memcommit.persistence.store.lookup.context_names import (
    list_context_and_descendant_names,
)
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True, slots=True)
class _CheckpointToken:
    owner: object
    contexts: tuple[Context, ...]


class MemoryStoreCheckpointPort:
    """Freeze and publish manual checkpoints in one Profile store."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store
        self._owner = object()

    def freeze(self, request: CheckpointRequest) -> CheckpointPlan:
        if request.context_locator is None:
            context_name = request.current_context_name
            if context_name is None:
                raise RuntimeError("No current context. Run 'mem init <name>' first.")
        else:
            context_name = resolve_existing_context_operand(
                freeze_local_context_operand_candidates(self._store),
                request.context_locator,
                current=request.current_context_name,
            ).name
        root = self._store.load_direct(context_name)
        if not request.recursive:
            contexts = (root,)
            expected_catalog = None
            checkpoint_uids: tuple[str | None, ...] = (None,)
        else:
            expected_catalog = tuple(self._store.list_context_names())
            context_names = list_context_and_descendant_names(
                (context_name,),
                expected_catalog,
            )
            contexts = tuple(
                root if name == context_name else self._store.load_direct(name)
                for name in context_names
            )
            checkpoint_uids = tuple(str(uuid.uuid4()) for _context in contexts)
        return CheckpointPlan(
            request=request,
            root_context_name=context_name,
            root_context_uid=root.uid,
            members=tuple(
                CheckpointMemberPlan(
                    context_name=context.name,
                    context_uid=context.uid,
                    checkpoint_uid=checkpoint_uid,
                )
                for context, checkpoint_uid in zip(contexts, checkpoint_uids)
            ),
            expected_context_catalog=expected_catalog,
            token=_CheckpointToken(owner=self._owner, contexts=contexts),
        )

    def apply(self, plan: CheckpointPlan) -> CheckpointResult:
        token = plan.token
        if not isinstance(token, _CheckpointToken) or token.owner is not self._owner:
            raise TypeError("Checkpoint plan token is invalid for this Store port.")
        if not plan.request.recursive:
            checkpoint = self._store.checkpoint(
                token.contexts[0],
                plan.request.checkpoint_message,
            )
            return CheckpointResult(
                root_context_name=plan.root_context_name,
                root_checkpoint_uid=checkpoint.uid,
                timestamp=checkpoint.timestamp,
                checkpoint_message=plan.request.checkpoint_message,
                recursive=False,
                member_count=1,
            )

        membership = [
            {"uid": member.context_uid, "name": member.context_name}
            for member in plan.members
        ]
        checkpoint_uids = tuple(member.checkpoint_uid for member in plan.members)
        assert all(uid is not None for uid in checkpoint_uids)
        root_checkpoint_uid = checkpoint_uids[0]
        assert root_checkpoint_uid is not None
        checkpoint_set = {
            "version": 2,
            # The physical root checkpoint is the one canonical recovery-unit
            # handle; a second receipt-only identity would split History and Revert.
            "uid": root_checkpoint_uid,
            "root": {
                "uid": plan.root_context_uid,
                "name": plan.root_context_name,
            },
            "include_descendants": True,
            "members": [
                {
                    "context_uid": member.context_uid,
                    "context_name": member.context_name,
                    "checkpoint_uid": member.checkpoint_uid,
                }
                for member in plan.members
            ],
        }
        checkpoints = self._store.checkpoint_context_batch(
            token.contexts,
            checkpoint_message=plan.request.checkpoint_message,
            command="checkpoint",
            command_details={
                "checkpoint_set": checkpoint_set,
                "command_contexts": membership,
            },
            expected_context_catalog=plan.expected_context_catalog,
            checkpoint_uids=(uid for uid in checkpoint_uids if uid is not None),
        )
        return CheckpointResult(
            root_context_name=plan.root_context_name,
            root_checkpoint_uid=root_checkpoint_uid,
            timestamp=checkpoints[0].timestamp,
            checkpoint_message=plan.request.checkpoint_message,
            recursive=True,
            member_count=len(checkpoints),
        )


def execute_checkpoint(
    store: MemoryStore,
    request: CheckpointRequest,
) -> CheckpointResult:
    """Freeze and publish one manual Checkpoint through the same Store port."""

    port = MemoryStoreCheckpointPort(store)
    plan = plan_checkpoint(request, port=port)
    return apply_checkpoint(plan, port=port)


__all__ = ["MemoryStoreCheckpointPort", "execute_checkpoint"]
