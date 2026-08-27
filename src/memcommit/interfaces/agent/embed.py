"""Versioned agent contract for live Context and Memory Embed links."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from memcommit.adapters.python_api import (
    EmbeddedContextResult,
    EmbeddedMemoryResult,
    EmbedAuthorityError,
    EmbedConflictError,
    EmbedContextError,
    EmbedError,
    EmbedExecutionError,
    EmbedInputError,
    EmbedStorageError,
    MemCommitClient,
)
from memcommit.interfaces.agent.contract import (
    AgentRequestError,
    JsonObject,
    error_response,
    exact_fields,
    object_value,
    text_value,
)


EMBED_AGENT_CONTRACT_VERSION = 1
EMBED_AGENT_TOOL_NAME = "memcommit_embed"
EmbedAgentKind = Literal["memory", "context"]


def _parse_request(payload: object) -> tuple[EmbedAgentKind, dict[str, object]]:
    value = object_value(payload, label="Embed request")
    version = value.get("version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != EMBED_AGENT_CONTRACT_VERSION
    ):
        raise AgentRequestError(
            f"version must be exactly {EMBED_AGENT_CONTRACT_VERSION}."
        )
    kind = value.get("kind")
    if kind == "memory":
        exact_fields(
            value,
            required={
                "version",
                "kind",
                "memory_selector",
                "source_context",
                "into_context",
            },
            optional=frozenset({"before", "after"}),
            label="Memory Embed request",
        )
        return "memory", {
            "memory_selector": text_value(
                value.get("memory_selector"), field="memory_selector"
            ),
            "source_context": text_value(
                value.get("source_context"), field="source_context"
            ),
            "into_context": text_value(
                value.get("into_context"), field="into_context"
            ),
            "before": text_value(value.get("before"), field="before", optional=True),
            "after": text_value(value.get("after"), field="after", optional=True),
        }
    if kind == "context":
        exact_fields(
            value,
            required={"version", "kind", "child_context", "into_context"},
            optional=frozenset({"before", "after"}),
            label="Context Embed request",
        )
        return "context", {
            "child_context": text_value(
                value.get("child_context"), field="child_context"
            ),
            "into_context": text_value(
                value.get("into_context"), field="into_context"
            ),
            "before": text_value(value.get("before"), field="before", optional=True),
            "after": text_value(value.get("after"), field="after", optional=True),
        }
    raise AgentRequestError("kind must be exactly memory or context.")


def _placement(result) -> JsonObject:
    return {
        "position": result.placement.position,
        "previous_uid": result.placement.previous_uid,
        "next_uid": result.placement.next_uid,
    }


def _serialize(result: EmbeddedMemoryResult | EmbeddedContextResult) -> JsonObject:
    if isinstance(result, EmbeddedMemoryResult):
        return {
            "embed_uid": result.embed_uid,
            "source_name": result.source_name,
            "source_uid": result.source_uid,
            "memory_uid": result.memory_uid,
            "into_name": result.into_name,
            "into_uid": result.into_uid,
            "placement": _placement(result),
            "checkpoint_uid": result.checkpoint_uid,
            "mode": "LIVE",
        }
    return {
        "child_name": result.child_name,
        "child_uid": result.child_uid,
        "into_name": result.into_name,
        "into_uid": result.into_uid,
        "placement": _placement(result),
        "checkpoint_uid": result.checkpoint_uid,
        "mode": "LIVE",
    }


_PUBLIC_ERRORS: tuple[tuple[type[EmbedError], str, str, bool], ...] = (
    (EmbedInputError, "invalid_request", "The Embed request is invalid.", True),
    (
        EmbedContextError,
        "context_unavailable",
        "A requested Embed Context is unavailable.",
        True,
    ),
    (
        EmbedAuthorityError,
        "authority_denied",
        "The active Profile does not authorize this Embed.",
        True,
    ),
    (
        EmbedConflictError,
        "concurrent_update",
        "The frozen Embed Source, Target, or gap changed.",
        False,
    ),
    (
        EmbedStorageError,
        "storage_failure",
        "Embed could not safely access durable state.",
        False,
    ),
    (
        EmbedExecutionError,
        "execution_failed",
        "Embed did not publish one complete live-link receipt.",
        False,
    ),
)


class EmbedAgentAdapter:
    """Translate explicit link kinds without guessing from a name string."""

    def __init__(self, client: MemCommitClient) -> None:
        if not isinstance(client, MemCommitClient):
            raise TypeError("EmbedAgentAdapter requires a MemCommitClient.")
        self._client = client

    def invoke(self, payload: object) -> JsonObject:
        kind: EmbedAgentKind | None = None
        if isinstance(payload, Mapping) and payload.get("kind") in (
            "memory",
            "context",
        ):
            kind = payload["kind"]  # type: ignore[assignment]
        try:
            kind, arguments = _parse_request(payload)
        except AgentRequestError as error:
            return error_response(
                version=EMBED_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="invalid_request",
                message=str(error),
                retryable=False,
            )
        try:
            result = (
                self._client.embed_memory(**arguments)  # type: ignore[arg-type]
                if kind == "memory"
                else self._client.embed_context(**arguments)  # type: ignore[arg-type]
            )
        except EmbedError as error:
            for error_type, code, message, expose in _PUBLIC_ERRORS:
                if isinstance(error, error_type):
                    return error_response(
                        version=EMBED_AGENT_CONTRACT_VERSION,
                        kind=kind,
                        code=code,
                        message=str(error) if expose else message,
                        retryable=False,
                    )
            return error_response(
                version=EMBED_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="embed_failed",
                message="Embed failed without a more specific public category.",
                retryable=False,
            )
        except Exception:
            return error_response(
                version=EMBED_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="internal_error",
                message="The Embed tool failed internally.",
                retryable=False,
            )
        return {
            "version": EMBED_AGENT_CONTRACT_VERSION,
            "ok": True,
            "kind": kind,
            "result": _serialize(result),
        }


def _request_schema(kind: EmbedAgentKind) -> JsonObject:
    text = {"type": "string", "minLength": 1, "pattern": r".*\S.*"}
    if kind == "memory":
        required = [
            "version",
            "kind",
            "memory_selector",
            "source_context",
            "into_context",
        ]
        properties = {
            "version": {"type": "integer", "const": EMBED_AGENT_CONTRACT_VERSION},
            "kind": {"type": "string", "const": "memory"},
            "memory_selector": text,
            "source_context": text,
            "into_context": text,
            "before": {**text, "type": ["string", "null"]},
            "after": {**text, "type": ["string", "null"]},
        }
    else:
        required = ["version", "kind", "child_context", "into_context"]
        properties = {
            "version": {"type": "integer", "const": EMBED_AGENT_CONTRACT_VERSION},
            "kind": {"type": "string", "const": "context"},
            "child_context": text,
            "into_context": text,
            "before": {**text, "type": ["string", "null"]},
            "after": {**text, "type": ["string", "null"]},
        }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


def embed_agent_tool_schema() -> JsonObject:
    """Return a strict tagged union for live Memory or Context links."""

    return {
        "name": EMBED_AGENT_TOOL_NAME,
        "description": (
            "Create an explicit live link to one Memory or Context in a local "
            "Target Context."
        ),
        "parameters": {"oneOf": [_request_schema("memory"), _request_schema("context")]},
    }


__all__ = [
    "EMBED_AGENT_CONTRACT_VERSION",
    "EMBED_AGENT_TOOL_NAME",
    "EmbedAgentAdapter",
    "EmbedAgentKind",
    "embed_agent_tool_schema",
]
