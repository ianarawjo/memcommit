"""Validate reviewed Merge results and publish their exact Target and checkpoint."""

from contextlib import ExitStack

from memcommit.application.authorization.context_operation import (
    authorized_context_operation,
)
from memcommit.application.context_access.access import GrantedReadStore
from memcommit.core.context import Context
from memcommit.persistence.store import context_record_digest

from .inputs import PreparedMerge
from .receipt import MergeReceipt, merge_receipt_summary
from .result import MergeResult


def validate_merge_result(prepared: PreparedMerge, result: MergeResult) -> None:
    """Validate phase bindings and destination authority without recalculation."""
    if not isinstance(prepared, PreparedMerge):
        raise TypeError("Merge requires its prepared inputs.")
    if not isinstance(result, MergeResult):
        raise ValueError("Merge requires a composed, verified Merge result.")
    result.validate(prepared)


def apply_merge(prepared: PreparedMerge, result: MergeResult) -> MergeReceipt:
    """Save the exact reviewed Target; the Store rejects repeated operation IDs."""
    validate_merge_result(prepared, result)
    inputs = prepared.inputs
    source_access, target_access = inputs.source_access, inputs.target_access
    target_store = target_access.store
    with (
        authorized_context_operation(
            (
                (source_access, ("READ",)),
                (target_access, _target_permissions(prepared, result)),
            )
        ) as registry,
        ExitStack() as locks,
    ):
        # The Target store locks local participants atomically. A Source owned by
        # another store must stay locked until that Target transaction finishes.
        if inputs.cross_profile_memory_only:
            locks.enter_context(
                source_access.store._context_graph_lock(exclusive=False)
            )
            locks.enter_context(
                source_access.store._context_write_locks((source_access.context_name,))
            )
        source = source_access.store.load_direct(source_access.context_name)
        raw_source_digest = context_record_digest(source)
        if source_access.is_granted:
            source = GrantedReadStore(source_access, registry=registry).project_direct(
                source, source_access.access_name
            )
        if (
            source.uid != inputs.source().uid
            or context_record_digest(source) != inputs.source_digest
        ):
            raise ValueError("The Merge Source changed after review.")
        target = target_store.load_direct(target_access.context_name)
        if (
            target.uid != inputs.target().uid
            or context_record_digest(target) != inputs.target_digest
        ):
            raise ValueError("The Merge Target changed after review.")
        if target_access.is_granted:
            visible = GrantedReadStore(target_access, registry=registry).project_direct(
                target, target_access.access_name
            )
            if visible.to_dict()["memories"] != target.to_dict()["memories"]:
                raise ValueError(
                    "Merge Target gained hidden direct items after review."
                )
            target = visible
        target.name = target_access.access_name
        if target.to_dict() != inputs.target().to_dict():
            raise ValueError(
                "Merge Preview no longer matches the frozen Target baseline."
            )

        # Resolve may use a temporary Context identity. Only that envelope changes;
        # every item value, identity and position is exactly the reviewed result.
        record = result.post_image.to_dict()
        record.update(uid=target.uid, name=target_access.context_name)
        post_target = Context.from_dict(record)
        bindings = (
            ()
            if inputs.cross_profile_memory_only
            else (
                (
                    source_access.context_name,
                    source.uid,
                    raw_source_digest,
                ),
            )
        )
        from .checkpoint import merge_checkpoint

        saved = target_store.save_merge_target(
            post_target,
            merge_checkpoint(prepared, result, post_target),
            expected_context_digest=inputs.target_digest,
            source_bindings=bindings,
        )
        if saved is None:
            raise RuntimeError("Merge Apply produced no checkpoint.")
    return MergeReceipt(
        inputs.operation_uid,
        target.uid,
        saved.uid,
        merge_receipt_summary(prepared, result),
    )


def _target_permissions(prepared, result):
    if prepared.request.method == "LITERAL":
        # Literal's established launch contract requires CREATE even for a no-op.
        return (
            ("CREATE", "UPDATE")
            if any(
                decision.kind == "TAKE_SOURCE"
                for round in result.rounds
                for decision in round.decisions.decisions
            )
            else ("CREATE",)
        )
    before, after = prepared.inputs.target(), result.post_image
    permissions = {"READ"}
    for uid in set(before.memories) | set(after.memories):
        old, new = before.memories.get(uid), after.memories.get(uid)
        if old is not None and new is not None and old.to_dict() == new.to_dict():
            continue
        permissions.add(
            "CREATE" if old is None else "DELETE" if new is None else "UPDATE"
        )
    return tuple(sorted(permissions))
