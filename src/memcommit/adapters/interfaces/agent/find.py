"""Versioned agent adapter for provider-free deterministic Find."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from memcommit.adapters.python_api import (
    FindAuthorityError,
    FindContextError,
    FindError,
    FindExecutionError,
    FindInputError,
    FindStorageError,
    MemCommitClient,
)
from memcommit.adapters.interfaces.agent.contract import (
    AgentRequestError,
    JsonObject,
    error_response,
    exact_fields,
    object_value,
    text_value,
)


FIND_AGENT_CONTRACT_VERSION = 1
FIND_AGENT_TOOL_NAME = "memcommit_find"
FindAgentKind = Literal["find"]


def _parse_request(
    payload: object,
) -> tuple[str, tuple[str, ...], bool, bool, bool, bool]:
    value = object_value(payload, label="Find request")
    version = value.get("version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != FIND_AGENT_CONTRACT_VERSION
    ):
        raise AgentRequestError(
            f"version must be exactly {FIND_AGENT_CONTRACT_VERSION}."
        )
    if value.get("kind") != "find":
        raise AgentRequestError("kind must be exactly find.")
    exact_fields(
        value,
        required={"version", "kind", "pattern"},
        optional=frozenset(
            {
                "context_names",
                "include_descendants",
                "follow_embeds",
                "regex",
                "ignore_case",
            }
        ),
        label="Find request",
    )
    names_value = value.get("context_names", [])
    if not isinstance(names_value, list) or any(
        not isinstance(name, str) or not name.strip() for name in names_value
    ):
        raise AgentRequestError("context_names must be an array of nonblank strings.")
    names = tuple(names_value)
    if len(set(names)) != len(names):
        raise AgentRequestError("context_names must not repeat.")
    booleans = tuple(
        value.get(field, False)
        for field in (
            "include_descendants",
            "follow_embeds",
            "regex",
            "ignore_case",
        )
    )
    if any(type(flag) is not bool for flag in booleans):
        raise AgentRequestError("Find mode and reach fields must be booleans.")
    return (
        text_value(value.get("pattern"), field="pattern"),
        names,
        *booleans,
    )


def _result(result) -> JsonObject:
    return {
        "pattern": result.pattern,
        "context_names": list(result.context_names),
        "include_descendants": result.include_descendants,
        "follow_embeds": result.follow_embeds,
        "mode": result.mode,
        "ignore_case": result.ignore_case,
        "scanned_item_count": result.scanned_item_count,
        "occurrence_count": result.occurrence_count,
        "matches": [
            {
                "context_name": match.context_name,
                "context_uid": match.context_uid,
                "kind": match.kind,
                "item_uid": match.item_uid,
                "content": match.content,
                "source_context_name": match.source_context_name,
                "source_context_uid": match.source_context_uid,
                "source_memory_uid": match.source_memory_uid,
                "spans": [
                    {"start": span.start, "end": span.end, "text": span.text}
                    for span in match.spans
                ],
            }
            for match in result.matches
        ],
        "effect": "NONE",
        "provider_used": False,
    }


_PUBLIC_ERRORS: tuple[tuple[type[FindError], str, str], ...] = (
    (FindInputError, "invalid_request", "The Find request is invalid."),
    (FindContextError, "context_unavailable", "A Find Context is unavailable."),
    (
        FindAuthorityError,
        "authority_denied",
        "The active Profile does not authorize this Find.",
    ),
    (FindStorageError, "storage_failure", "Find could not safely read the Store."),
    (
        FindExecutionError,
        "execution_failed",
        "Authorized Find did not return a complete result.",
    ),
)


class FindAgentAdapter:
    """Translate one versioned payload to the public deterministic Find facade."""

    def __init__(self, client: MemCommitClient) -> None:
        if not isinstance(client, MemCommitClient):
            raise TypeError("FindAgentAdapter requires a MemCommitClient.")
        self._client = client

    def invoke(self, payload: object) -> JsonObject:
        kind: FindAgentKind | None = None
        if isinstance(payload, Mapping) and payload.get("kind") == "find":
            kind = "find"
        try:
            pattern, names, descendants, embeds, regex, ignore_case = _parse_request(
                payload
            )
        except AgentRequestError as error:
            return error_response(
                version=FIND_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="invalid_request",
                message=str(error),
                retryable=False,
            )
        try:
            result = self._client.find(
                pattern,
                names,
                include_descendants=descendants,
                follow_embeds=embeds,
                regex=regex,
                ignore_case=ignore_case,
            )
        except FindError as error:
            for error_type, code, message in _PUBLIC_ERRORS:
                if isinstance(error, error_type):
                    return error_response(
                        version=FIND_AGENT_CONTRACT_VERSION,
                        kind=kind,
                        code=code,
                        message=(
                            str(error)
                            if isinstance(error, (FindInputError, FindContextError))
                            else message
                        ),
                        retryable=False,
                    )
            return error_response(
                version=FIND_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="find_failed",
                message="Find failed without a more specific public category.",
                retryable=False,
            )
        except Exception:
            return error_response(
                version=FIND_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="internal_error",
                message="The Find tool failed internally.",
                retryable=False,
            )
        return {
            "version": FIND_AGENT_CONTRACT_VERSION,
            "ok": True,
            "kind": kind,
            "result": _result(result),
        }


def find_agent_tool_schema() -> JsonObject:
    return {
        "name": FIND_AGENT_TOOL_NAME,
        "description": (
            "Find literal text or explicit regular-expression matches in a "
            "readable Context scope. This operation never uses a provider, "
            "semantic cache, visible session, or mutation."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["version", "kind", "pattern"],
            "properties": {
                "version": {
                    "type": "integer",
                    "const": FIND_AGENT_CONTRACT_VERSION,
                },
                "kind": {"type": "string", "const": "find"},
                "pattern": {"type": "string", "minLength": 1, "maxLength": 2000},
                "context_names": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "minLength": 1,
                        "pattern": r".*\S.*",
                    },
                    "uniqueItems": True,
                    "default": [],
                },
                "include_descendants": {"type": "boolean", "default": False},
                "follow_embeds": {"type": "boolean", "default": False},
                "regex": {"type": "boolean", "default": False},
                "ignore_case": {"type": "boolean", "default": False},
            },
        },
    }


__all__ = [
    "FIND_AGENT_CONTRACT_VERSION",
    "FIND_AGENT_TOOL_NAME",
    "FindAgentAdapter",
    "FindAgentKind",
    "find_agent_tool_schema",
]
