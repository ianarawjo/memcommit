"""Public application assembly for the unified Delete operation."""

from __future__ import annotations

from memcommit.adapters.python_api._runtime import ClientRuntime
from memcommit.adapters.python_api._support.errors import raise_public
from memcommit.adapters.python_api.delete import (
    ContextDeletePlanResult,
    ContextDeleteReceipt,
    DeletedDirectItemResult,
    DirectItemDeleteReceipt,
)
from memcommit.adapters.python_api.errors import (
    DeleteAuthorityError,
    DeleteConflictError,
    DeleteContextError,
    DeleteExecutionError,
    DeleteInputError,
    DeleteStorageError,
)
from memcommit.application.operations.delete.application import (
    ContextDeleteRequest,
    DeleteError,
    DeleteInputError as InternalDeleteInputError,
    DeleteStalePlanError,
    DirectItemDeleteRequest,
    apply_context_delete as apply_internal_context_delete,
    prepare_context_delete as prepare_internal_context_delete,
    run_direct_item_delete,
)
from memcommit.application.operations.delete.runtime import MemoryStoreDeletePort
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import ConcurrentContextUpdateError
from memcommit.application.capabilities.authority.write_protection import WriteProtectionError


def _item(item) -> DeletedDirectItemResult:
    return DeletedDirectItemResult(
        kind=item.kind,
        uid=item.uid,
        content=item.content,
        name=item.name,
        target_context_name=item.target_context_name,
        target_memory_uid=item.target_memory_uid,
    )


def remove_item(
    runtime: ClientRuntime,
    selector: str,
    *,
    context_name: str | None = None,
) -> DirectItemDeleteReceipt:
    """Remove one exact direct item and publish one normal checkpoint."""

    try:
        port = MemoryStoreDeletePort.capture(runtime.store)
        result = run_direct_item_delete(
            DirectItemDeleteRequest(
                selector=selector,
                context_locator=context_name,
            ),
            port=port,
        )
        return DirectItemDeleteReceipt(
            context_name=result.context_name,
            context_uid=result.context_uid,
            item=_item(result.item),
            checkpoint_uid=result.checkpoint_uid,
        )
    except (InternalDeleteInputError, KeyError, TypeError, ValueError) as error:
        raise_public(DeleteInputError, error)
    except FileNotFoundError as error:
        raise_public(DeleteContextError, error)
    except (ProfileConfigError, ProfileError, WriteProtectionError) as error:
        raise_public(DeleteAuthorityError, error)
    except ConcurrentContextUpdateError as error:
        raise_public(DeleteConflictError, error)
    except OSError as error:
        raise_public(DeleteStorageError, error)
    except (DeleteError, RuntimeError) as error:
        raise_public(DeleteExecutionError, error)
    raise AssertionError("unreachable")


def plan_context_delete(
    runtime: ClientRuntime,
    context_name: str,
) -> ContextDeletePlanResult:
    """Freeze one exact local Context and every permanent effect for review."""

    try:
        port = MemoryStoreDeletePort.capture(runtime.store)
        plan = prepare_internal_context_delete(
            ContextDeleteRequest(context_locator=context_name),
            port=port,
        )
        return ContextDeletePlanResult(
            context_name=plan.context_name,
            context_uid=plan.context_uid,
            context_digest=plan.context_digest,
            plan_digest=plan.plan_digest,
            descendants_preserved=plan.descendants_preserved,
            checkpoint_history_deleted=plan.checkpoint_history_deleted,
            restorable_snapshot_retained=plan.restorable_snapshot_retained,
            lifecycle_metadata_retained=plan.lifecycle_metadata_retained,
            _handle=(runtime, plan, port),
        )
    except (InternalDeleteInputError, TypeError, ValueError) as error:
        raise_public(DeleteInputError, error)
    except FileNotFoundError as error:
        raise_public(DeleteContextError, error)
    except (ProfileConfigError, ProfileError, WriteProtectionError) as error:
        raise_public(DeleteAuthorityError, error)
    except OSError as error:
        raise_public(DeleteStorageError, error)
    except (DeleteError, RuntimeError) as error:
        raise_public(DeleteExecutionError, error)
    raise AssertionError("unreachable")


def apply_context_delete(
    runtime: ClientRuntime,
    reviewed: ContextDeletePlanResult,
) -> ContextDeleteReceipt:
    """Apply one exact plan created by this client or publish no new effect."""

    if not isinstance(reviewed, ContextDeletePlanResult):
        raise DeleteInputError("Delete Apply requires a ContextDeletePlanResult.")
    try:
        handle = reviewed._handle
        if (
            not isinstance(handle, tuple)
            or len(handle) != 3
            or handle[0] is not runtime
            or not isinstance(handle[2], MemoryStoreDeletePort)
        ):
            raise DeleteInputError(
                "Delete Context plan does not belong to this MemCommitClient."
            )
        _root, plan, port = handle
        if (
            reviewed.context_name != plan.context_name
            or reviewed.context_uid != plan.context_uid
            or reviewed.context_digest != plan.context_digest
            or reviewed.plan_digest != plan.plan_digest
        ):
            raise DeleteInputError(
                "Delete Context plan was modified after review."
            )
        result = apply_internal_context_delete(plan, port=port)
        return ContextDeleteReceipt(
            status=result.status,
            context_name=result.context_name,
            context_uid=result.context_uid,
            context_digest=result.context_digest,
            plan_digest=result.plan_digest,
            event_uid=result.event_uid,
            operation_id=result.operation_id,
            previous_checkpoint_status=result.previous_checkpoint_status,
            descendants_preserved=result.descendants_preserved,
            cleanup_warning=result.cleanup_warning,
        )
    except (DeleteInputError, DeleteConflictError):
        raise
    except (ConcurrentContextUpdateError, DeleteStalePlanError) as error:
        raise_public(DeleteConflictError, error)
    except FileNotFoundError as error:
        raise_public(DeleteContextError, error)
    except (ProfileConfigError, ProfileError, WriteProtectionError) as error:
        raise_public(DeleteAuthorityError, error)
    except OSError as error:
        raise_public(DeleteStorageError, error)
    except (InternalDeleteInputError, TypeError, ValueError) as error:
        raise_public(DeleteInputError, error)
    except (DeleteError, RuntimeError) as error:
        raise_public(DeleteExecutionError, error)
    raise AssertionError("unreachable")


__all__ = ["apply_context_delete", "plan_context_delete", "remove_item"]
