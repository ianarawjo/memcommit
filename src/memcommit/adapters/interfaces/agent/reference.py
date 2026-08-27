"""Versioned agent contract for immutable Memory or Context snapshots."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from memcommit.adapters.python_api import (
    ContextReferenceResult,
    MemCommitClient,
    MemoryReferenceResult,
    ReferenceAuthorityError,
    ReferenceConflictError,
    ReferenceContextError,
    ReferenceError,
    ReferenceExecutionError,
    ReferenceInputError,
    ReferenceStorageError,
)
from memcommit.adapters.interfaces.agent.contract import (
    AgentRequestError,
    JsonObject,
    error_response,
    exact_fields,
    object_value,
    text_value,
)


REFERENCE_AGENT_CONTRACT_VERSION = 2
REFERENCE_AGENT_TOOL_NAME = "memcommit_reference"
ReferenceAgentKind = Literal["memory", "context"]


def _boolean(value: object, *, field: str, default: bool = False) -> bool:
    if value is None:
        return default
    if type(value) is not bool:
        raise AgentRequestError(f"{field} must be a boolean.")
    return value


def _parse_request(
    payload: object,
) -> tuple[ReferenceAgentKind, dict[str, object]]:
    value = object_value(payload, label="Reference request")
    version = value.get("version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != REFERENCE_AGENT_CONTRACT_VERSION
    ):
        raise AgentRequestError(
            f"version must be exactly {REFERENCE_AGENT_CONTRACT_VERSION}."
        )
    kind = value.get("kind")
    if kind == "memory":
        exact_fields(
            value,
            required={"version", "kind", "memory_selector", "source_context"},
            optional=frozenset({"into_context"}),
            label="Memory Reference request",
        )
        return "memory", {
            "memory_selector": text_value(
                value.get("memory_selector"), field="memory_selector"
            ),
            "source_context": text_value(
                value.get("source_context"), field="source_context"
            ),
            "into_context": text_value(
                value.get("into_context"), field="into_context", optional=True
            ),
        }
    if kind == "context":
        exact_fields(
            value,
            required={"version", "kind", "source_context"},
            optional=frozenset({"into_context", "recursive"}),
            label="Context Reference request",
        )
        return "context", {
            "source_context": text_value(
                value.get("source_context"), field="source_context"
            ),
            "into_context": text_value(
                value.get("into_context"), field="into_context", optional=True
            ),
            "recursive": _boolean(value.get("recursive"), field="recursive"),
        }
    raise AgentRequestError("kind must be exactly memory or context.")


def _serialize(
    result: MemoryReferenceResult | ContextReferenceResult,
) -> JsonObject:
    if isinstance(result, ContextReferenceResult):
        return {
            "reference_uid": result.reference_uid,
            "source_name": result.source_name,
            "source_uid": result.source_uid,
            "snapshot_content_sha256": result.snapshot_content_sha256,
            "include_descendants": result.include_descendants,
            "follow_embeds": result.follow_embeds,
            "context_count": result.context_count,
            "into_name": result.into_name,
            "into_uid": result.into_uid,
            "checkpoint_uid": result.checkpoint_uid,
            "mode": "SNAPSHOT",
        }
    return {
        "reference_uid": result.reference_uid,
        "source_name": result.source_name,
        "source_uid": result.source_uid,
        "memory_uid": result.memory_uid,
        "memory_content_sha256": result.memory_content_sha256,
        "into_name": result.into_name,
        "into_uid": result.into_uid,
        "checkpoint_uid": result.checkpoint_uid,
        "mode": "SNAPSHOT",
    }


_PUBLIC_ERRORS: tuple[tuple[type[ReferenceError], str, str, bool], ...] = (
    (ReferenceInputError, "invalid_request", "The Reference request is invalid.", True),
    (
        ReferenceContextError,
        "context_unavailable",
        "A requested Reference Context is unavailable.",
        True,
    ),
    (
        ReferenceAuthorityError,
        "authority_denied",
        "The active Profile does not authorize this Reference.",
        True,
    ),
    (
        ReferenceConflictError,
        "concurrent_update",
        "The frozen Reference Source or Target changed before publication.",
        False,
    ),
    (
        ReferenceStorageError,
        "storage_failure",
        "Reference could not safely access local durable state.",
        False,
    ),
    (
        ReferenceExecutionError,
        "execution_failed",
        "Reference did not publish one complete snapshot receipt.",
        False,
    ),
)


class ReferenceAgentAdapter:
    """Translate one explicit snapshot unit to the public facade."""

    def __init__(self, client: MemCommitClient) -> None:
        if not isinstance(client, MemCommitClient):
            raise TypeError("ReferenceAgentAdapter requires a MemCommitClient.")
        self._client = client

    def invoke(self, payload: object) -> JsonObject:
        kind: ReferenceAgentKind | None = None
        if isinstance(payload, Mapping) and payload.get("kind") in (
            "memory",
            "context",
        ):
            kind = payload["kind"]  # type: ignore[assignment]
        try:
            kind, arguments = _parse_request(payload)
        except AgentRequestError as error:
            return error_response(
                version=REFERENCE_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="invalid_request",
                message=str(error),
                retryable=False,
            )
        try:
            result = (
                self._client.reference_memory(**arguments)  # type: ignore[arg-type]
                if kind == "memory"
                else self._client.reference_context(**arguments)  # type: ignore[arg-type]
            )
        except ReferenceError as error:
            for error_type, code, message, expose in _PUBLIC_ERRORS:
                if isinstance(error, error_type):
                    return error_response(
                        version=REFERENCE_AGENT_CONTRACT_VERSION,
                        kind=kind,
                        code=code,
                        message=str(error) if expose else message,
                        retryable=False,
                    )
            return error_response(
                version=REFERENCE_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="reference_failed",
                message="Reference failed without a more specific public category.",
                retryable=False,
            )
        except Exception:
            return error_response(
                version=REFERENCE_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="internal_error",
                message="The Reference tool failed internally.",
                retryable=False,
            )
        return {
            "version": REFERENCE_AGENT_CONTRACT_VERSION,
            "ok": True,
            "kind": kind,
            "result": _serialize(result),
        }


def reference_agent_tool_schema() -> JsonObject:
    """Return a fresh strict tagged union for one immutable snapshot."""

    text = {"type": "string", "minLength": 1, "pattern": r".*\S.*"}
    return {
        "name": REFERENCE_AGENT_TOOL_NAME,
        "description": (
            "Copy one exact Source Memory or direct/recursive Context scope "
            "into a local Target as an immutable snapshot."
        ),
        "parameters": {
            "oneOf": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "version",
                        "kind",
                        "memory_selector",
                        "source_context",
                    ],
                    "properties": {
                        "version": {
                            "type": "integer",
                            "const": REFERENCE_AGENT_CONTRACT_VERSION,
                        },
                        "kind": {"type": "string", "const": "memory"},
                        "memory_selector": text,
                        "source_context": text,
                        "into_context": {**text, "type": ["string", "null"]},
                    },
                },
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["version", "kind", "source_context"],
                    "properties": {
                        "version": {
                            "type": "integer",
                            "const": REFERENCE_AGENT_CONTRACT_VERSION,
                        },
                        "kind": {"type": "string", "const": "context"},
                        "source_context": text,
                        "into_context": {**text, "type": ["string", "null"]},
                        "recursive": {"type": "boolean", "default": False},
                    },
                },
            ]
        },
    }


__all__ = [
    "REFERENCE_AGENT_CONTRACT_VERSION",
    "REFERENCE_AGENT_TOOL_NAME",
    "ReferenceAgentAdapter",
    "ReferenceAgentKind",
    "reference_agent_tool_schema",
]
