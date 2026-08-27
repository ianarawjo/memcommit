"""Versioned read-only agent adapter for exact Show inspection."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from memcommit.adapters.python_api import (
    MemCommitClient,
    ShowAuthorityError,
    ShowContextError,
    ShowContextResult,
    ShowError,
    ShowExecutionError,
    ShowInputError,
    ShowMemoryReferenceResult,
    ShowMemoryResult,
    ShowQueryViewResult,
    ShowSourceResult,
    ShowStorageError,
)
from memcommit.interfaces.agent.contract import (
    AgentRequestError,
    JsonObject,
    error_response,
    exact_fields,
    object_value,
    text_value,
)


SHOW_AGENT_CONTRACT_VERSION = 1
SHOW_AGENT_TOOL_NAME = "memcommit_show"
ShowAgentKind = Literal["inspect"]


def _parse_request(payload: object) -> tuple[ShowAgentKind, str | None, str | None]:
    value = object_value(payload, label="Show request")
    version = value.get("version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != SHOW_AGENT_CONTRACT_VERSION
    ):
        raise AgentRequestError(
            f"version must be exactly {SHOW_AGENT_CONTRACT_VERSION}."
        )
    if value.get("kind") != "inspect":
        raise AgentRequestError("kind must be exactly inspect.")
    exact_fields(
        value,
        required={"version", "kind"},
        optional=frozenset({"context_name", "selector"}),
        label="Show inspect request",
    )
    return (
        "inspect",
        text_value(
            value.get("context_name"),
            field="context_name",
            optional=True,
        ),
        text_value(value.get("selector"), field="selector", optional=True),
    )


def _source(source: ShowSourceResult) -> JsonObject:
    return {
        "access": source.access,
        "reach": source.reach,
        "form": source.form,
        "states": list(source.states),
        "permissions": list(source.permissions),
    }


def _item(item) -> JsonObject:
    if isinstance(item, ShowMemoryResult):
        return {
            "kind": item.kind,
            "uid": item.uid,
            "context_name": item.context_name,
            "content": item.content,
            "source": _source(item.source),
        }
    if isinstance(item, ShowMemoryReferenceResult):
        return {
            "kind": item.kind,
            "uid": item.uid,
            "context_name": item.context_name,
            "target_context_uid": item.target_context_uid,
            "target_context_name": item.target_context_name,
            "target_memory_uid": item.target_memory_uid,
            "resolved": item.resolved,
            "content": item.content,
            "source": _source(item.source),
        }
    if isinstance(item, ShowQueryViewResult):
        return {
            "kind": item.kind,
            "uid": item.uid,
            "context_name": item.context_name,
            "name": item.name,
            "source": _source(item.source),
        }
    return {
        "kind": item.kind,
        "uid": item.uid,
        "context_name": item.context_name,
        "name": item.name,
        "source": _source(item.source),
    }


def _result(result) -> JsonObject:
    if isinstance(result, ShowContextResult):
        return {
            "kind": result.kind,
            "uid": result.uid,
            "name": result.name,
            "items": [_item(item) for item in result.items],
            "source": _source(result.source),
            "effect": "NONE",
        }
    return {**_item(result), "effect": "NONE"}


_PUBLIC_ERRORS: tuple[tuple[type[ShowError], str, str], ...] = (
    (ShowInputError, "invalid_request", "The Show request is invalid."),
    (
        ShowContextError,
        "context_unavailable",
        "The requested Show Context is unavailable.",
    ),
    (
        ShowAuthorityError,
        "authority_denied",
        "The active Profile does not authorize this Show.",
    ),
    (
        ShowStorageError,
        "storage_failure",
        "Show could not safely read local durable state.",
    ),
    (
        ShowExecutionError,
        "execution_failed",
        "Authorized Show did not return a complete result.",
    ),
)


class ShowAgentAdapter:
    """Translate one exact inspection payload to the public Show facade."""

    def __init__(self, client: MemCommitClient) -> None:
        if not isinstance(client, MemCommitClient):
            raise TypeError("ShowAgentAdapter requires a MemCommitClient.")
        self._client = client

    def invoke(self, payload: object) -> JsonObject:
        kind: ShowAgentKind | None = None
        if isinstance(payload, Mapping) and payload.get("kind") == "inspect":
            kind = "inspect"
        try:
            kind, context_name, selector = _parse_request(payload)
        except AgentRequestError as error:
            return error_response(
                version=SHOW_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="invalid_request",
                message=str(error),
                retryable=False,
            )
        try:
            result = self._client.show(selector, context_name=context_name)
        except ShowError as error:
            for error_type, code, message in _PUBLIC_ERRORS:
                if isinstance(error, error_type):
                    return error_response(
                        version=SHOW_AGENT_CONTRACT_VERSION,
                        kind=kind,
                        code=code,
                        message=(
                            str(error)
                            if isinstance(
                                error,
                                (ShowInputError, ShowContextError),
                            )
                            else message
                        ),
                        retryable=False,
                    )
            return error_response(
                version=SHOW_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="show_failed",
                message="Show failed without a more specific public category.",
                retryable=False,
            )
        except Exception:
            return error_response(
                version=SHOW_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="internal_error",
                message="The Show tool failed internally.",
                retryable=False,
            )
        return {
            "version": SHOW_AGENT_CONTRACT_VERSION,
            "ok": True,
            "kind": kind,
            "result": _result(result),
        }


def show_agent_tool_schema() -> JsonObject:
    nonblank_text = {
        "type": ["string", "null"],
        "minLength": 1,
        "pattern": r".*\S.*",
    }
    return {
        "name": SHOW_AGENT_TOOL_NAME,
        "description": (
            "Read one exact MemCommit Context or direct item. The result is "
            "read-only, includes source/access facts, and never reveals "
            "query-only source content."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["version", "kind"],
            "properties": {
                "version": {
                    "type": "integer",
                    "const": SHOW_AGENT_CONTRACT_VERSION,
                },
                "kind": {"type": "string", "const": "inspect"},
                "context_name": nonblank_text,
                "selector": nonblank_text,
            },
        },
    }


__all__ = [
    "SHOW_AGENT_CONTRACT_VERSION",
    "SHOW_AGENT_TOOL_NAME",
    "ShowAgentAdapter",
    "ShowAgentKind",
    "show_agent_tool_schema",
]
