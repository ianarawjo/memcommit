"""Publish reviewed flat Resolve effects back to their frozen real owners."""

from __future__ import annotations


from memcommit.application.authorization.context_operation import (
    authorized_context_operation,
)
from memcommit.application.capabilities.context_memory_target import ContextMemoryTarget
from memcommit.application.capabilities.context_scope_loading import (
    load_mutable_context_scope,
    walk_context_owners,
)
from memcommit.application.context_access import authority_context_name
from memcommit.application.context_access.access import grant_checkpoint_args
from memcommit.application.capabilities.semantic.changes import (
    get_required_permission_for_effect,
)
from memcommit.application.context_access.readable_contexts import (
    freeze_readable_context_catalog,
)
from memcommit.application.operations.resolve.model import (
    RESOLVE_CONTRACT_VERSION,
    ResolveAuthorityError,
    ResolveConflictError,
    ResolveError,
    ResolveReceipt,
)
from memcommit.application.operations.update.application import apply_update
from memcommit.application.operations.update.model import (
    AddOperation,
    EditOperation,
    RemoveOperation,
)
from memcommit.core.context import AutoCheckpoint
from memcommit.persistence.operations.update.publication_repository import (
    _apply_operations_to_direct,
)
from memcommit.persistence.store import _write_json_atomic, context_record_digest


def _owner_records(graph):
    return tuple(
        sorted(
            (owner.uid, owner.name, owner._store_digest or context_record_digest(owner))
            for owner in walk_context_owners(graph)
        )
    )


def revalidate_recursive_target(adapter, frame, *, registry=None):
    """Bind owner membership and every direct record, including unchanged owners."""
    access = adapter._revalidated_access(frame)
    graph = load_mutable_context_scope(adapter.active_store, access, registry=registry)
    required_permissions = {
        "READ",
        *(get_required_permission_for_effect(effect) for effect in frame.allowed_effects),
    }
    if access.view is not None and not required_permissions <= set(
        access.view.grant.permissions
    ):
        raise ResolveAuthorityError("Resolve Grant lost required authority.")
    if (
        _owner_records(graph) != _owner_records(frame.memory_target.graph)
        or ContextMemoryTarget.from_context(graph).analysis_context().to_dict()
        != frame.source.context().to_dict()
    ):
        raise ResolveConflictError(
            "The recursive Resolve target changed during review. Reopen Resolve."
        )
    return access, graph


def publish_recursive_resolve(
    adapter,
    frame,
    plan,
    *,
    unresolved_issue_uids,
    finalized_inputs,
    removed_item_uids,
    memory_origins,
):
    """Apply all owner effects under one command lock, rolling back failed saves."""
    if removed_item_uids:
        raise ResolveError("Recursive Resolve contains only Memory effects.")
    merged = {origin.analysis_uid: origin for origin in frame.memory_target.origins}
    for origin in memory_origins:
        if origin.analysis_uid in merged and merged[origin.analysis_uid] != origin:
            raise ResolveError("Reviewed Memory placement changed before Apply.")
        merged[origin.analysis_uid] = origin
    target = ContextMemoryTarget(
        frame.memory_target.graph,
        tuple(merged.values()),
        frame.memory_target.analysis_context_uid,
    )
    owner_plan = target.owner_update_plan(plan)
    effect_types = {
        AddOperation: "CREATE",
        EditOperation: "UPDATE",
        RemoveOperation: "DELETE",
    }
    effects = tuple(
        effect_types.get(type(operation)) for operation in owner_plan.operations
    )
    if any(effect not in frame.allowed_effects for effect in effects):
        raise ResolveAuthorityError(
            "Resolve UpdatePlan exceeds the finalized effect capabilities."
        )
    access, _ = revalidate_recursive_target(adapter, frame)
    catalog = freeze_readable_context_catalog(
        adapter.active_store, access, include_query_routes=False
    )
    uses_by_name = {}
    for operation, effect in zip(owner_plan.operations, effects, strict=True):
        uses_by_name.setdefault(operation.owner_context_name, {"READ"}).add(
            get_required_permission_for_effect(effect)
        )
    if not uses_by_name:
        uses_by_name[target.graph.name] = {
            "READ",
            get_required_permission_for_effect(frame.allowed_effects[0]),
        }
    checks = tuple(
        (catalog.access_for(name), tuple(sorted(uses)))
        for name, uses in uses_by_name.items()
    )
    store = access.store

    def physical_name(name):
        return (
            authority_context_name(frame.granted_binding, name)
            if frame.granted_binding
            else name
        )

    lock_names = {
        physical_name(owner.name) for owner in walk_context_owners(target.graph)
    }
    checkpoints = []
    originals = {}
    written = []
    with authorized_context_operation(checks) as registry:
        with store._command_write_lock():
            store._assert_profile_write_allowed()
            with store._context_write_locks(lock_names):
                _access, current_graph = revalidate_recursive_target(
                    adapter, frame, registry=registry
                )
                apply_update(owner_plan, current_graph)
                post_images = {}
                digests = {}
                for name in uses_by_name:
                    physical = physical_name(name)
                    direct = store.load_direct(physical)
                    operations = tuple(
                        op
                        for op in owner_plan.operations
                        if op.owner_context_name == name
                    )
                    inbound = adapter._inbound_references(
                        store,
                        context_uid=direct.uid,
                        deleted_uids={
                            op.memory_uid
                            for op in operations
                            if isinstance(op, RemoveOperation)
                        },
                    )
                    if inbound:
                        raise ResolveConflictError(
                            "Resolve cannot delete Memories with inbound references: "
                            + ", ".join(f"{owner}#{uid[:8]}" for owner, uid in inbound)
                        )
                    originals[physical] = direct.to_dict()
                    digests[physical] = context_record_digest(direct)
                    # Save actual direct records: lexical loading adds analysis-only
                    # edges which must never turn into persisted Context embeds.
                    post_images[physical] = _apply_operations_to_direct(
                        direct, operations
                    )
                membership = [
                    {
                        "uid": post_images[physical_name(name)].uid,
                        "name": physical_name(name),
                    }
                    for name in uses_by_name
                ]
                try:
                    for name in uses_by_name:
                        physical = physical_name(name)
                        written.append(physical)
                        checkpoint = store._save_locked(
                            post_images[physical],
                            AutoCheckpoint(
                                command="resolve",
                                args={
                                    "contract": RESOLVE_CONTRACT_VERSION,
                                    "revision": frame.revision,
                                    "recursive": True,
                                    "resolve_operation_uid": plan.uid,
                                    "update_plan_uid": plan.uid,
                                    "update_plan_digest": plan.digest,
                                    "command_contexts": membership,
                                    "removed_item_uids": [],
                                    "effects": [
                                        op.to_dict()
                                        for op in owner_plan.operations
                                        if op.owner_context_name == name
                                    ],
                                    "finalized_inputs": [
                                        value.to_dict() for value in finalized_inputs
                                    ],
                                    "unresolved_issue_uids": list(
                                        unresolved_issue_uids
                                    ),
                                    "guidance": frame.request.guidance,
                                    **grant_checkpoint_args(access),
                                },
                                description=f"Resolved recursive target {frame.display_name} from finalized decisions",
                            ),
                            expected_context_digest=digests[physical],
                        )
                        if checkpoint is None:
                            raise ResolveError("Resolve Apply produced no checkpoint.")
                        checkpoints.append((name, checkpoint.uid))
                except Exception:
                    rollback_error = None
                    for physical in written:
                        try:
                            _write_json_atomic(
                                store._context_file(physical), originals[physical]
                            )
                        except Exception as error:
                            rollback_error = rollback_error or error
                    for name, uid in checkpoints:
                        try:
                            store._remove_checkpoint_uid_locked(
                                physical_name(name), uid
                            )
                        except Exception as error:
                            rollback_error = rollback_error or error
                    if rollback_error:
                        raise ResolveError(
                            "Resolve failed and could not fully roll back its target."
                        ) from rollback_error
                    raise
    return ResolveReceipt(
        context_uid=target.graph.uid,
        context_name=frame.display_name,
        revision=frame.revision,
        plan_uid=plan.uid,
        checkpoint_uid=checkpoints[0][1],
        created_uids=tuple(
            op.memory_uid
            for op in owner_plan.operations
            if isinstance(op, AddOperation)
        ),
        updated_uids=tuple(
            op.memory_uid
            for op in owner_plan.operations
            if isinstance(op, EditOperation)
        ),
        deleted_uids=tuple(
            op.memory_uid
            for op in owner_plan.operations
            if isinstance(op, RemoveOperation)
        ),
        unresolved_issue_uids=unresolved_issue_uids,
        checkpoints=tuple(checkpoints),
    )
