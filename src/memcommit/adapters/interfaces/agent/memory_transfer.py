"""Versioned JSON-safe agent adapters for direct-Memory Copy and Move."""

from __future__ import annotations

from collections.abc import Mapping

from memcommit.adapters.python_api import (
    MemCommitClient,
    MemoryTransferAuthorityError,
    MemoryTransferConflictError,
    MemoryTransferContextError,
    MemoryTransferError,
    MemoryTransferExecutionError,
    MemoryTransferInputError,
    MemoryTransferStorageError,
)
from memcommit.adapters.interfaces.agent.contract import (
    AgentRequestError,
    JsonObject,
    error_response,
    exact_fields,
    object_value,
    text_value,
)


MEMORY_TRANSFER_AGENT_CONTRACT_VERSION = 2
COPY_MEMORIES_AGENT_TOOL_NAME = "memcommit_copy_memories"
MOVE_MEMORIES_AGENT_TOOL_NAME = "memcommit_move_memories"


def _optional_text(value: Mapping[str, object], field: str) -> str | None:
    result = text_value(value.get(field), field=field, optional=True)
    if result is not None and len(result) > 1000:
        raise AgentRequestError(f"{field} must be at most 1000 characters.")
    return result


def _common_request(
    payload: object,
    *,
    label: str,
    extra_optional: frozenset[str],
) -> tuple[dict[str, object], tuple[str, ...]]:
    value = object_value(payload, label=label)
    version = value.get("version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != MEMORY_TRANSFER_AGENT_CONTRACT_VERSION
    ):
        raise AgentRequestError(
            f"version must be exactly {MEMORY_TRANSFER_AGENT_CONTRACT_VERSION}."
        )
    exact_fields(
        value,
        required={"version", "memory_locators"},
        optional=frozenset(
            {
                "source_context",
                "into_context",
                "before",
                "after",
                *extra_optional,
            }
        ),
        label=label,
    )
    raw_locators = value.get("memory_locators")
    if not isinstance(raw_locators, list) or not raw_locators:
        raise AgentRequestError("memory_locators must be a nonempty list.")
    locators = tuple(
        text_value(item, field="memory_locators item") for item in raw_locators
    )
    if any(len(locator) > 1000 for locator in locators):
        raise AgentRequestError(
            "Each memory_locators item must be at most 1000 characters."
        )
    return dict(value), locators


def _bool(value: Mapping[str, object], field: str) -> bool:
    candidate = value.get(field, False)
    if not isinstance(candidate, bool):
        raise AgentRequestError(f"{field} must be a boolean.")
    return candidate


def _result(receipt, *, kind: str) -> JsonObject:
    result: JsonObject = {
        "into_context_name": receipt.into_context_name,
        "into_context_uid": receipt.into_context_uid,
        "count": receipt.count,
        "placement": {
            "position": receipt.placement.position,
            "previous_uid": receipt.placement.previous_uid,
            "next_uid": receipt.placement.next_uid,
        },
        "items": [
            {
                "source_context_name": item.source_context_name,
                "source_context_uid": item.source_context_uid,
                "source_memory_uid": item.source_memory_uid,
                "into_memory_uid": item.into_memory_uid,
            }
            for item in receipt.items
        ],
        "plan_digest": receipt.plan_digest,
        "checkpoints": [
            {
                "context_name": checkpoint.context_name,
                "context_uid": checkpoint.context_uid,
                "checkpoint_uid": checkpoint.checkpoint_uid,
            }
            for checkpoint in receipt.checkpoints
        ],
        "undoable": receipt.undoable,
        "provider_used": False,
    }
    if kind == "copy":
        result["effect"] = "CHECKPOINTED_MEMORY_COPY"
    elif kind == "move":
        result.update(
            {
                "link_policy": receipt.link_policy,
                "inbound_link_count": receipt.inbound_link_count,
                "retargeted_link_count": receipt.retargeted_link_count,
                "dangling_link_count": receipt.dangling_link_count,
                "effect": "CHECKPOINTED_MEMORY_MOVE",
            }
        )
    else:
        raise ValueError(f"Unknown Memory transfer result kind '{kind}'.")
    return result


_PUBLIC_ERRORS: tuple[tuple[type[MemoryTransferError], str, str, bool], ...] = (
    (
        MemoryTransferInputError,
        "invalid_request",
        "The Memory transfer request is invalid.",
        False,
    ),
    (
        MemoryTransferContextError,
        "context_unavailable",
        "A Memory transfer Source or Target is unavailable.",
        False,
    ),
    (
        MemoryTransferAuthorityError,
        "authority_denied",
        "The active Profile or protection policy denies this transfer.",
        False,
    ),
    (
        MemoryTransferConflictError,
        "concurrent_update",
        "The exact Source, Target, or link graph changed before Apply.",
        True,
    ),
    (
        MemoryTransferStorageError,
        "storage_failure",
        "Memory transfer could not safely access durable state.",
        False,
    ),
    (
        MemoryTransferExecutionError,
        "execution_failed",
        "Memory transfer returned no complete durable receipt.",
        False,
    ),
)


class MemoryTransferAgentAdapter:
    def __init__(self, client: MemCommitClient) -> None:
        if not isinstance(client, MemCommitClient):
            raise TypeError("MemoryTransferAgentAdapter requires a MemCommitClient.")
        self._client = client

    @staticmethod
    def _error(error: MemoryTransferError, *, kind: str) -> JsonObject:
        for error_type, code, message, retryable in _PUBLIC_ERRORS:
            if isinstance(error, error_type):
                visible = (
                    str(error)
                    if isinstance(
                        error,
                        (
                            MemoryTransferInputError,
                            MemoryTransferContextError,
                            MemoryTransferAuthorityError,
                            MemoryTransferConflictError,
                        ),
                    )
                    else message
                )
                return error_response(
                    version=MEMORY_TRANSFER_AGENT_CONTRACT_VERSION,
                    kind=kind,
                    code=code,
                    message=visible,
                    retryable=retryable,
                )
        return error_response(
            version=MEMORY_TRANSFER_AGENT_CONTRACT_VERSION,
            kind=kind,
            code="memory_transfer_failed",
            message="Memory transfer failed without a specific public category.",
            retryable=False,
        )

    def copy(self, payload: object) -> JsonObject:
        kind = "copy"
        try:
            value, locators = _common_request(
                payload,
                label="Copy Memories request",
                extra_optional=frozenset(),
            )
            arguments = {
                "memory_locators": locators,
                "source_context": _optional_text(value, "source_context"),
                "into_context": _optional_text(value, "into_context"),
                "before": _optional_text(value, "before"),
                "after": _optional_text(value, "after"),
            }
        except AgentRequestError as error:
            return error_response(
                version=MEMORY_TRANSFER_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="invalid_request",
                message=str(error),
                retryable=False,
            )
        try:
            result = _result(self._client.copy_memories(**arguments), kind=kind)
        except MemoryTransferError as error:
            return self._error(error, kind=kind)
        except Exception:
            return error_response(
                version=MEMORY_TRANSFER_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="internal_error",
                message="The Memory Copy tool failed internally.",
                retryable=False,
            )
        return {
            "version": MEMORY_TRANSFER_AGENT_CONTRACT_VERSION,
            "ok": True,
            "kind": kind,
            "result": result,
        }

    def move(self, payload: object) -> JsonObject:
        kind = "move"
        try:
            value, locators = _common_request(
                payload,
                label="Move Memories request",
                extra_optional=frozenset({"retarget_links", "break_links"}),
            )
            arguments = {
                "memory_locators": locators,
                "source_context": _optional_text(value, "source_context"),
                "into_context": _optional_text(value, "into_context"),
                "before": _optional_text(value, "before"),
                "after": _optional_text(value, "after"),
                "retarget_links": _bool(value, "retarget_links"),
                "break_links": _bool(value, "break_links"),
            }
        except AgentRequestError as error:
            return error_response(
                version=MEMORY_TRANSFER_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="invalid_request",
                message=str(error),
                retryable=False,
            )
        try:
            result = _result(self._client.move_memories(**arguments), kind=kind)
        except MemoryTransferError as error:
            return self._error(error, kind=kind)
        except Exception:
            return error_response(
                version=MEMORY_TRANSFER_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="internal_error",
                message="The Memory Move tool failed internally.",
                retryable=False,
            )
        return {
            "version": MEMORY_TRANSFER_AGENT_CONTRACT_VERSION,
            "ok": True,
            "kind": kind,
            "result": result,
        }


def _properties(extra: dict[str, object]) -> dict[str, object]:
    optional_text = {"type": "string", "minLength": 1, "maxLength": 1000}
    return {
        "version": {
            "type": "integer",
            "const": MEMORY_TRANSFER_AGENT_CONTRACT_VERSION,
        },
        "memory_locators": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "string",
                "minLength": 1,
                "maxLength": 1000,
            },
        },
        "source_context": optional_text,
        "into_context": optional_text,
        "before": optional_text,
        "after": optional_text,
        **extra,
    }


def copy_memories_agent_tool_schema() -> JsonObject:
    return {
        "name": COPY_MEMORIES_AGENT_TOOL_NAME,
        "description": (
            "Copy an ordered batch of directly owned local Memories into one "
            "existing local Target as independent editable ordinary Memories."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["version", "memory_locators"],
            "properties": _properties({}),
        },
    }


def move_memories_agent_tool_schema() -> JsonObject:
    return {
        "name": MOVE_MEMORIES_AGENT_TOOL_NAME,
        "description": (
            "Move an ordered batch of directly owned local Memories into one "
            "distinct local Target as one Undoable atomic command. Local live "
            "Memory Embeds follow by default; snapshots remain unchanged."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["version", "memory_locators"],
            "properties": _properties(
                {
                    "retarget_links": {
                        "type": "boolean",
                        "description": "Compatibility spelling for default retargeting.",
                    },
                    "break_links": {
                        "type": "boolean",
                        "description": "Explicitly allow live Embeds to become dangling.",
                    },
                }
            ),
        },
    }


__all__ = [
    "COPY_MEMORIES_AGENT_TOOL_NAME",
    "MEMORY_TRANSFER_AGENT_CONTRACT_VERSION",
    "MOVE_MEMORIES_AGENT_TOOL_NAME",
    "MemoryTransferAgentAdapter",
    "copy_memories_agent_tool_schema",
    "move_memories_agent_tool_schema",
]
