"""Versioned agent adapters for the unified Delete operation."""

from __future__ import annotations

from memcommit.adapters.python_api import (
    DeleteAuthorityError,
    DeleteConflictError,
    DeleteContextError,
    DeleteError,
    DeleteExecutionError,
    DeleteInputError,
    DeleteStorageError,
    MemCommitClient,
)
from memcommit.adapters.agent.contract import (
    AgentRequestError,
    JsonObject,
    error_response,
    exact_fields,
    object_value,
    text_value,
)


DELETE_AGENT_CONTRACT_VERSION = 1
REMOVE_ITEM_AGENT_TOOL_NAME = "memcommit_remove_item"
PLAN_CONTEXT_DELETE_AGENT_TOOL_NAME = "memcommit_plan_context_delete"
APPLY_CONTEXT_DELETE_AGENT_TOOL_NAME = "memcommit_delete_context"


def _request(payload: object, *, label: str, required: set[str]) -> JsonObject:
    value = object_value(payload, label=label)
    version = value.get("version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != DELETE_AGENT_CONTRACT_VERSION
    ):
        raise AgentRequestError(
            f"version must be exactly {DELETE_AGENT_CONTRACT_VERSION}."
        )
    exact_fields(
        value,
        required={"version", *required},
        optional=frozenset(),
        label=label,
    )
    return dict(value)


def _context_name(value: object) -> str:
    name = text_value(value, field="context_name")
    if len(name) > 1000:
        raise AgentRequestError("context_name must be at most 1000 characters.")
    return name


def _plan_result(plan) -> JsonObject:
    return {
        "context_name": plan.context_name,
        "context_uid": plan.context_uid,
        "context_digest": plan.context_digest,
        "plan_digest": plan.plan_digest,
        "effects": {
            "checkpoint_history_deleted": plan.checkpoint_history_deleted,
            "descendants_preserved": plan.descendants_preserved,
            "lifecycle_metadata_retained": plan.lifecycle_metadata_retained,
            "restorable_snapshot_retained": plan.restorable_snapshot_retained,
        },
        "effect": "NONE",
        "provider_used": False,
    }


def _item_result(receipt) -> JsonObject:
    item = receipt.item
    return {
        "context_name": receipt.context_name,
        "context_uid": receipt.context_uid,
        "item": {
            "kind": item.kind,
            "uid": item.uid,
            "content": item.content,
            "name": item.name,
            "target_context_name": item.target_context_name,
            "target_memory_uid": item.target_memory_uid,
        },
        "checkpoint_uid": receipt.checkpoint_uid,
        "undoable": receipt.undoable,
        "effect": "CHECKPOINTED_ITEM_REMOVAL",
        "provider_used": False,
    }


def _context_result(receipt) -> JsonObject:
    return {
        "status": receipt.status,
        "context_name": receipt.context_name,
        "context_uid": receipt.context_uid,
        "context_digest": receipt.context_digest,
        "plan_digest": receipt.plan_digest,
        "event_uid": receipt.event_uid,
        "operation_id": receipt.operation_id,
        "previous_checkpoint_status": receipt.previous_checkpoint_status,
        "descendants_preserved": receipt.descendants_preserved,
        "cleanup_warning": receipt.cleanup_warning,
        "undoable": receipt.undoable,
        "effect": "CONTEXT_PERMANENTLY_DELETED",
        "provider_used": False,
    }


_PUBLIC_ERRORS: tuple[tuple[type[DeleteError], str, str, bool], ...] = (
    (DeleteInputError, "invalid_request", "The Delete request is invalid.", False),
    (
        DeleteContextError,
        "context_unavailable",
        "The Delete target is unavailable.",
        False,
    ),
    (
        DeleteAuthorityError,
        "authority_denied",
        "The active Profile, Grant, or protection policy denies Delete.",
        False,
    ),
    (
        DeleteConflictError,
        "stale_plan",
        "The exact Delete target changed; prepare a new plan before retrying.",
        True,
    ),
    (
        DeleteStorageError,
        "storage_failure",
        "Delete could not safely use the Store.",
        False,
    ),
    (
        DeleteExecutionError,
        "execution_failed",
        "Delete returned no complete durable receipt.",
        False,
    ),
)


class DeleteAgentAdapter:
    """Expose separately classifiable read, mutable, and destructive calls."""

    def __init__(self, client: MemCommitClient) -> None:
        if not isinstance(client, MemCommitClient):
            raise TypeError("DeleteAgentAdapter requires a MemCommitClient.")
        self._client = client

    def _error(self, error: DeleteError, *, kind: str) -> JsonObject:
        for error_type, code, message, retryable in _PUBLIC_ERRORS:
            if isinstance(error, error_type):
                visible = (
                    str(error)
                    if isinstance(
                        error,
                        (DeleteInputError, DeleteContextError, DeleteConflictError),
                    )
                    else message
                )
                return error_response(
                    version=DELETE_AGENT_CONTRACT_VERSION,
                    kind=kind,
                    code=code,
                    message=visible,
                    retryable=retryable,
                )
        return error_response(
            version=DELETE_AGENT_CONTRACT_VERSION,
            kind=kind,
            code="delete_failed",
            message="Delete failed without a more specific public category.",
            retryable=False,
        )

    def remove_item(self, payload: object) -> JsonObject:
        kind = "remove_item"
        try:
            value = object_value(payload, label="Remove item request")
            version = value.get("version")
            if version != DELETE_AGENT_CONTRACT_VERSION or isinstance(version, bool):
                raise AgentRequestError("version must be exactly 1.")
            exact_fields(
                value,
                required={"version", "selector"},
                optional=frozenset({"context_name"}),
                label="Remove item request",
            )
            selector = text_value(value.get("selector"), field="selector")
            if len(selector) > 1000:
                raise AgentRequestError("selector must be at most 1000 characters.")
            raw_context = value.get("context_name")
            context_name = (
                None if raw_context is None else _context_name(raw_context)
            )
        except AgentRequestError as error:
            return error_response(
                version=DELETE_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="invalid_request",
                message=str(error),
                retryable=False,
            )
        try:
            result = _item_result(
                self._client.remove_item(selector, context_name=context_name)
            )
        except DeleteError as error:
            return self._error(error, kind=kind)
        except Exception:
            return error_response(
                version=DELETE_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="internal_error",
                message="The Delete item tool failed internally.",
                retryable=False,
            )
        return {
            "version": DELETE_AGENT_CONTRACT_VERSION,
            "ok": True,
            "kind": kind,
            "result": result,
        }

    def plan_context(self, payload: object) -> JsonObject:
        kind = "plan_context"
        try:
            value = _request(
                payload,
                label="Plan Context delete request",
                required={"context_name"},
            )
            context_name = _context_name(value.get("context_name"))
        except AgentRequestError as error:
            return error_response(
                version=DELETE_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="invalid_request",
                message=str(error),
                retryable=False,
            )
        try:
            result = _plan_result(self._client.plan_context_delete(context_name))
        except DeleteError as error:
            return self._error(error, kind=kind)
        except Exception:
            return error_response(
                version=DELETE_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="internal_error",
                message="The Delete planning tool failed internally.",
                retryable=False,
            )
        return {
            "version": DELETE_AGENT_CONTRACT_VERSION,
            "ok": True,
            "kind": kind,
            "result": result,
        }

    def apply_context(self, payload: object) -> JsonObject:
        kind = "apply_context"
        try:
            value = _request(
                payload,
                label="Apply Context delete request",
                required={"context_name", "expected_plan_digest"},
            )
            context_name = _context_name(value.get("context_name"))
            expected = text_value(
                value.get("expected_plan_digest"),
                field="expected_plan_digest",
            )
            if (
                len(expected) != 64
                or any(character not in "0123456789abcdef" for character in expected)
            ):
                raise AgentRequestError(
                    "expected_plan_digest must be a 64-character lowercase digest."
                )
        except AgentRequestError as error:
            return error_response(
                version=DELETE_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="invalid_request",
                message=str(error),
                retryable=False,
            )
        try:
            # Re-freeze immediately after the host-approved call arrives. The
            # reviewed digest binds the canonical identity and exact record, so
            # a changed target fails before the destructive Store primitive.
            plan = self._client.plan_context_delete(context_name)
            if plan.plan_digest != expected:
                raise DeleteConflictError(
                    "The current Context deletion plan does not match "
                    "expected_plan_digest."
                )
            result = _context_result(self._client.apply_context_delete(plan))
        except DeleteError as error:
            return self._error(error, kind=kind)
        except Exception:
            return error_response(
                version=DELETE_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="internal_error",
                message="The Delete Context tool failed internally.",
                retryable=False,
            )
        return {
            "version": DELETE_AGENT_CONTRACT_VERSION,
            "ok": True,
            "kind": kind,
            "result": result,
        }


def remove_item_agent_tool_schema() -> JsonObject:
    return {
        "name": REMOVE_ITEM_AGENT_TOOL_NAME,
        "description": (
            "Remove one direct item from an authorized Context. The operation "
            "writes one normal checkpoint and can be undone with Context Undo."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["version", "selector"],
            "properties": {
                "version": {"type": "integer", "const": 1},
                "selector": {"type": "string", "minLength": 1, "maxLength": 1000},
                "context_name": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 1000,
                },
            },
        },
    }


def plan_context_delete_agent_tool_schema() -> JsonObject:
    return {
        "name": PLAN_CONTEXT_DELETE_AGENT_TOOL_NAME,
        "description": (
            "Read and freeze one exact local Context deletion plan. This changes "
            "nothing and returns the canonical name, identity, record digest, "
            "permanent effects, and approval-bound plan digest."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["version", "context_name"],
            "properties": {
                "version": {"type": "integer", "const": 1},
                "context_name": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 1000,
                },
            },
        },
    }


def apply_context_delete_agent_tool_schema() -> JsonObject:
    return {
        "name": APPLY_CONTEXT_DELETE_AGENT_TOOL_NAME,
        "description": (
            "Permanently delete the exact local Context named by a prior plan. "
            "This destroys its checkpoint history and cannot be undone; a host "
            "should obtain user approval for this destructive tool call."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["version", "context_name", "expected_plan_digest"],
            "properties": {
                "version": {"type": "integer", "const": 1},
                "context_name": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 1000,
                },
                "expected_plan_digest": {
                    "type": "string",
                    "pattern": "^[0-9a-f]{64}$",
                },
            },
        },
    }


__all__ = [
    "APPLY_CONTEXT_DELETE_AGENT_TOOL_NAME",
    "DELETE_AGENT_CONTRACT_VERSION",
    "PLAN_CONTEXT_DELETE_AGENT_TOOL_NAME",
    "REMOVE_ITEM_AGENT_TOOL_NAME",
    "DeleteAgentAdapter",
    "apply_context_delete_agent_tool_schema",
    "plan_context_delete_agent_tool_schema",
    "remove_item_agent_tool_schema",
]
