"""Versioned JSON-safe agent adapter for the public Add facade."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from memcommit.adapters.python_api import (
    AddAuthorityError,
    AddConflictError,
    AddContextError,
    AddError,
    AddExecutionError,
    AddInputError,
    AddMemoriesResult,
    AddStorageError,
    MemCommitClient,
)
from memcommit.interfaces.agent.contract import (
    AGENT_ERROR_MESSAGE_LIMIT,
    AgentRequestError,
    JsonObject,
    error_response,
    exact_fields,
    object_value,
    text_value,
)


ADD_AGENT_CONTRACT_VERSION = 1
ADD_AGENT_TOOL_NAME = "memcommit_add_memories"
ADD_AGENT_ERROR_MESSAGE_LIMIT = AGENT_ERROR_MESSAGE_LIMIT
AddAgentKind = Literal["memories"]


def _parse_request(payload: object) -> tuple[AddAgentKind, dict[str, object]]:
    value = object_value(payload, label="Add request")
    version = value.get("version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != ADD_AGENT_CONTRACT_VERSION
    ):
        raise AgentRequestError(
            f"version must be exactly {ADD_AGENT_CONTRACT_VERSION}."
        )
    if value.get("kind") != "memories":
        raise AgentRequestError("kind must be exactly memories.")
    exact_fields(
        value,
        required={"version", "kind", "contents"},
        optional=frozenset({"context_name"}),
        label="Add memories request",
    )
    raw_contents = value["contents"]
    if not isinstance(raw_contents, list) or not raw_contents:
        raise AgentRequestError("contents must be a nonempty list of Memory texts.")
    contents = tuple(
        text_value(content, field="contents item") for content in raw_contents
    )
    context_name = text_value(
        value.get("context_name"),
        field="context_name",
        optional=True,
    )
    return "memories", {
        "contents": contents,
        "context_name": context_name,
    }


def _serialize_result(result: AddMemoriesResult) -> JsonObject:
    return {
        "context_name": result.context_name,
        "context_uid": result.context_uid,
        "count": result.count,
        "memories": [
            {"uid": memory.uid, "content": memory.content} for memory in result.memories
        ],
        "checkpoint_uid": result.checkpoint_uid,
    }


_PUBLIC_ERRORS: tuple[
    tuple[type[AddError], str, str, bool],
    ...,
] = (
    (AddInputError, "invalid_request", "The Add request is invalid.", False),
    (
        AddContextError,
        "context_unavailable",
        "The requested Add target Context is unavailable.",
        False,
    ),
    (
        AddAuthorityError,
        "authority_denied",
        "The active Profile does not authorize this Add.",
        False,
    ),
    (
        AddConflictError,
        "concurrent_update",
        "The Add target changed before the checkpoint could commit.",
        False,
    ),
    (
        AddStorageError,
        "storage_failure",
        "Add could not safely access local durable state.",
        False,
    ),
    (
        AddExecutionError,
        "execution_failed",
        "Authorized Add execution did not produce a complete receipt.",
        False,
    ),
)


def _error_result(
    *,
    kind: AddAgentKind | None,
    code: str,
    message: str,
    retryable: bool = False,
) -> JsonObject:
    return error_response(
        version=ADD_AGENT_CONTRACT_VERSION,
        kind=kind,
        code=code,
        message=message,
        retryable=retryable,
    )


class AddAgentAdapter:
    """Translate one exact batch payload to one public Add call."""

    def __init__(self, client: MemCommitClient) -> None:
        if not isinstance(client, MemCommitClient):
            raise TypeError("AddAgentAdapter requires a MemCommitClient.")
        self._client = client

    def invoke(self, payload: object) -> JsonObject:
        kind: AddAgentKind | None = None
        if isinstance(payload, Mapping) and payload.get("kind") == "memories":
            kind = "memories"
        try:
            kind, arguments = _parse_request(payload)
        except AgentRequestError as error:
            return _error_result(
                kind=kind,
                code="invalid_request",
                message=str(error),
            )

        try:
            result = self._client.add_memories(**arguments)  # type: ignore[arg-type]
        except AddError as error:
            for error_type, code, message, retryable in _PUBLIC_ERRORS:
                if isinstance(error, error_type):
                    return _error_result(
                        kind=kind,
                        code=code,
                        message=(
                            str(error)
                            if isinstance(
                                error,
                                (AddInputError, AddContextError, AddAuthorityError),
                            )
                            else message
                        ),
                        retryable=retryable,
                    )
            return _error_result(
                kind=kind,
                code="add_failed",
                message="Add failed without a more specific public category.",
            )
        except Exception:
            # A mutation tool must not expose host paths or infer that an
            # unknown failure is safe to retry.
            return _error_result(
                kind=kind,
                code="internal_error",
                message="The Add tool failed internally.",
            )

        return {
            "version": ADD_AGENT_CONTRACT_VERSION,
            "ok": True,
            "kind": kind,
            "result": _serialize_result(result),
        }


def add_agent_tool_schema() -> JsonObject:
    """Return a fresh function-tool schema for one exact Add batch."""

    nonblank_text = {
        "type": "string",
        "minLength": 1,
        "pattern": r".*\S.*",
    }
    return {
        "name": ADD_AGENT_TOOL_NAME,
        "description": (
            "Append one exact ordered Memory batch to one MemCommit Context "
            "and publish one Add checkpoint."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["version", "kind", "contents"],
            "properties": {
                "version": {
                    "type": "integer",
                    "const": ADD_AGENT_CONTRACT_VERSION,
                },
                "kind": {"type": "string", "const": "memories"},
                "contents": {
                    "type": "array",
                    "minItems": 1,
                    "items": nonblank_text,
                },
                "context_name": {
                    "type": ["string", "null"],
                    "minLength": 1,
                    "pattern": r".*\S.*",
                },
            },
        },
    }


__all__ = [
    "ADD_AGENT_CONTRACT_VERSION",
    "ADD_AGENT_ERROR_MESSAGE_LIMIT",
    "ADD_AGENT_TOOL_NAME",
    "AddAgentAdapter",
    "AddAgentKind",
    "add_agent_tool_schema",
]
