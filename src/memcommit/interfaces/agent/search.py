"""Versioned agent adapter for provider-backed semantic Search."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from memcommit.api import (
    MemCommitClient,
    SemanticAuthorityError,
    SemanticContextError,
    SemanticError,
    SemanticExecutionError,
    SemanticInputError,
    SemanticProviderFailure,
    SemanticStorageError,
)
from memcommit.interfaces.agent.contract import (
    AgentRequestError,
    JsonObject,
    error_response,
    exact_fields,
    object_value,
    text_value,
)


SEARCH_AGENT_CONTRACT_VERSION = 1
SEARCH_AGENT_TOOL_NAME = "memcommit_search"
SearchAgentKind = Literal["search"]


def _parse_request(
    payload: object,
) -> tuple[str, tuple[str, ...], bool, bool, int]:
    value = object_value(payload, label="Search request")
    version = value.get("version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != SEARCH_AGENT_CONTRACT_VERSION
    ):
        raise AgentRequestError(
            f"version must be exactly {SEARCH_AGENT_CONTRACT_VERSION}."
        )
    if value.get("kind") != "search":
        raise AgentRequestError("kind must be exactly search.")
    exact_fields(
        value,
        required={"version", "kind", "query"},
        optional=frozenset(
            {
                "context_names",
                "include_descendants",
                "follow_embeds",
                "limit",
            }
        ),
        label="Search request",
    )
    names_value = value.get("context_names", [])
    if not isinstance(names_value, list) or any(
        not isinstance(name, str) or not name.strip() for name in names_value
    ):
        raise AgentRequestError("context_names must be an array of nonblank strings.")
    names = tuple(names_value)
    if len(set(names)) != len(names):
        raise AgentRequestError("context_names must not repeat.")
    include_descendants = value.get("include_descendants", False)
    follow_embeds = value.get("follow_embeds", False)
    if not isinstance(include_descendants, bool) or not isinstance(
        follow_embeds, bool
    ):
        raise AgentRequestError("Search reach fields must be booleans.")
    limit = value.get("limit", 5)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
        raise AgentRequestError("limit must be an integer from 1 through 20.")
    return (
        text_value(value.get("query"), field="query"),
        names,
        include_descendants,
        follow_embeds,
        limit,
    )


def _result(result) -> JsonObject:
    return {
        "query": result.query,
        "context_names": list(result.context_names),
        "include_descendants": result.include_descendants,
        "follow_embeds": result.follow_embeds,
        "mode": result.mode,
        "related_query": result.related_query,
        "items": [
            {
                "context_name": item.context_name,
                "kind": item.kind,
                "uid": item.uid,
                "content": item.content,
                "relevance": item.relevance,
                "source_context_name": item.source_context_name,
                "source_context_uid": item.source_context_uid,
                "source_memory_uid": item.source_memory_uid,
            }
            for item in result.items
        ],
        "effect": "NONE",
    }


_PUBLIC_ERRORS: tuple[tuple[type[SemanticError], str, str], ...] = (
    (SemanticInputError, "invalid_request", "The Search request is invalid."),
    (
        SemanticContextError,
        "context_unavailable",
        "A requested Search Context is unavailable.",
    ),
    (
        SemanticAuthorityError,
        "authority_denied",
        "The active Profile does not authorize this Search.",
    ),
    (
        SemanticProviderFailure,
        "provider_failure",
        "The semantic Search provider could not complete the request.",
    ),
    (
        SemanticStorageError,
        "storage_failure",
        "Search could not safely read local durable state.",
    ),
    (
        SemanticExecutionError,
        "execution_failed",
        "Authorized Search did not return a complete result.",
    ),
)


class SearchAgentAdapter:
    """Translate one versioned payload to the public Search facade."""

    def __init__(self, client: MemCommitClient) -> None:
        if not isinstance(client, MemCommitClient):
            raise TypeError("SearchAgentAdapter requires a MemCommitClient.")
        self._client = client

    def invoke(self, payload: object) -> JsonObject:
        kind: SearchAgentKind | None = None
        if isinstance(payload, Mapping) and payload.get("kind") == "search":
            kind = "search"
        try:
            query, names, descendants, embeds, limit = _parse_request(payload)
        except AgentRequestError as error:
            return error_response(
                version=SEARCH_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="invalid_request",
                message=str(error),
                retryable=False,
            )
        try:
            result = self._client.search(
                query,
                names,
                include_descendants=descendants,
                follow_embeds=embeds,
                limit=limit,
            )
        except SemanticError as error:
            for error_type, code, message in _PUBLIC_ERRORS:
                if isinstance(error, error_type):
                    return error_response(
                        version=SEARCH_AGENT_CONTRACT_VERSION,
                        kind=kind,
                        code=code,
                        message=(
                            str(error)
                            if isinstance(error, (SemanticInputError, SemanticContextError))
                            else message
                        ),
                        retryable=isinstance(error, SemanticProviderFailure),
                    )
            return error_response(
                version=SEARCH_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="search_failed",
                message="Search failed without a more specific public category.",
                retryable=False,
            )
        except Exception:
            return error_response(
                version=SEARCH_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="internal_error",
                message="The Search tool failed internally.",
                retryable=False,
            )
        return {
            "version": SEARCH_AGENT_CONTRACT_VERSION,
            "ok": True,
            "kind": kind,
            "result": _result(result),
        }


def search_agent_tool_schema() -> JsonObject:
    return {
        "name": SEARCH_AGENT_TOOL_NAME,
        "description": (
            "Semantically rank Memories in an explicit readable Context scope. "
            "This may use a provider or an exact cache and never mutates Contexts."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["version", "kind", "query"],
            "properties": {
                "version": {
                    "type": "integer",
                    "const": SEARCH_AGENT_CONTRACT_VERSION,
                },
                "kind": {"type": "string", "const": "search"},
                "query": {
                    "type": "string",
                    "minLength": 1,
                    "pattern": r".*\S.*",
                },
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
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20,
                    "default": 5,
                },
            },
        },
    }


__all__ = [
    "SEARCH_AGENT_CONTRACT_VERSION",
    "SEARCH_AGENT_TOOL_NAME",
    "SearchAgentAdapter",
    "SearchAgentKind",
    "search_agent_tool_schema",
]
