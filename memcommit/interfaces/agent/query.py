"""Versioned JSON-safe agent adapter for the public Query facade."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from memcommit.api import (
    GrantedQueryResult,
    MemCommitClient,
    MemCommitError,
    OrdinaryQueryResult,
    QueryAuthorityError,
    QueryConfigurationError,
    QueryContextError,
    QueryExecutionError,
    QueryInputError,
    QueryProviderFailure,
    QueryPublicationError,
    QueryStorageError,
    ReferenceQueryResult,
)
from memcommit.context import QueryContextRef
from memcommit.interfaces.agent.contract import (
    AGENT_ERROR_MESSAGE_LIMIT,
    AgentRequestError as _AgentRequestError,
    JsonObject,
    error_response,
    exact_fields as _exact_fields,
    object_value as _object,
    text_value as _text,
)


QUERY_AGENT_CONTRACT_VERSION = 1
QUERY_AGENT_TOOL_NAME = "memcommit_query"
QUERY_AGENT_ERROR_MESSAGE_LIMIT = AGENT_ERROR_MESSAGE_LIMIT
QueryAgentKind = Literal["ordinary", "granted", "reference"]


def _boolean(value: object, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise _AgentRequestError(f"{field} must be a boolean.")
    return value


def _optional_text(
    payload: Mapping[str, object],
    field: str,
) -> str | None:
    return _text(payload.get(field), field=field, optional=True)


def _ordinary_arguments(payload: Mapping[str, object]) -> dict[str, object]:
    _exact_fields(
        payload,
        required={"version", "kind", "question"},
        optional=frozenset({"context_names", "include_descendants", "follow_embeds"}),
        label="ordinary Query request",
    )
    context_names: tuple[str, ...] | None = None
    if "context_names" in payload:
        raw_names = payload["context_names"]
        if not isinstance(raw_names, list):
            raise _AgentRequestError("context_names must be a list of names.")
        context_names = tuple(
            _text(name, field="context_names item") for name in raw_names
        )
        if not context_names:
            raise _AgentRequestError("context_names must not be empty.")
    return {
        "question": _text(payload["question"], field="question"),
        "context_names": context_names,
        "include_descendants": _boolean(
            payload.get("include_descendants", False),
            field="include_descendants",
        ),
        "follow_embeds": _boolean(
            payload.get("follow_embeds", True),
            field="follow_embeds",
        ),
    }


def _granted_arguments(payload: Mapping[str, object]) -> dict[str, object]:
    _exact_fields(
        payload,
        required={"version", "kind", "public_name"},
        optional=frozenset(
            {
                "question",
                "language",
                "session_name",
                "memory_handle",
                "federate_descendants",
            }
        ),
        label="granted Query request",
    )
    return {
        "public_name": _text(payload["public_name"], field="public_name"),
        "question": _optional_text(payload, "question"),
        "language": _text(payload.get("language", "en"), field="language"),
        "session_name": _optional_text(payload, "session_name"),
        "memory_handle": _optional_text(payload, "memory_handle"),
        "federate_descendants": _boolean(
            payload.get("federate_descendants", True),
            field="federate_descendants",
        ),
    }


def _reference_arguments(payload: Mapping[str, object]) -> dict[str, object]:
    _exact_fields(
        payload,
        required={"version", "kind", "reference", "question"},
        optional=frozenset({"language"}),
        label="reference Query request",
    )
    reference = _object(payload["reference"], label="reference")
    _exact_fields(
        reference,
        required={"uid", "name", "target_source_uid", "provider"},
        label="reference",
    )
    return {
        "reference": QueryContextRef(
            uid=_text(reference["uid"], field="reference.uid"),
            name=_text(reference["name"], field="reference.name"),
            target_source_uid=_text(
                reference["target_source_uid"],
                field="reference.target_source_uid",
            ),
            provider=_text(
                reference["provider"],
                field="reference.provider",
            ),
        ),
        "question": _text(payload["question"], field="question"),
        "language": _text(payload.get("language", "en"), field="language"),
    }


def _parse_request(
    payload: object,
) -> tuple[QueryAgentKind, dict[str, object]]:
    value = _object(payload, label="Query request")
    version = value.get("version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != QUERY_AGENT_CONTRACT_VERSION
    ):
        raise _AgentRequestError(
            f"version must be exactly {QUERY_AGENT_CONTRACT_VERSION}."
        )
    kind = value.get("kind")
    if kind == "ordinary":
        return kind, _ordinary_arguments(value)
    if kind == "granted":
        return kind, _granted_arguments(value)
    if kind == "reference":
        return kind, _reference_arguments(value)
    raise _AgentRequestError("kind must be one of: ordinary, granted, reference.")


def _ordinary_result(result: OrdinaryQueryResult) -> JsonObject:
    return {
        "answer": result.answer,
        "grounded": result.grounded,
        "citations": [
            {
                "number": citation.number,
                "alias": citation.alias,
                "context_name": citation.context_name,
                "kind": citation.kind,
                "uid": citation.uid,
                "content": citation.content,
            }
            for citation in result.citations
        ],
    }


def _granted_result(result: GrantedQueryResult) -> JsonObject:
    receipt = result.session_receipt
    return {
        "mode": result.mode,
        "public_name": result.public_name,
        "answer": result.answer,
        "catalog": [
            {
                "handle": entry.handle,
                "placeholder_lines": list(entry.placeholder_lines),
            }
            for entry in result.catalog
        ],
        "session_receipt": (
            {
                "session_name": receipt.session_name,
                "revision": receipt.revision,
                "turn_count": receipt.turn_count,
            }
            if receipt is not None
            else None
        ),
    }


def _reference_result(result: ReferenceQueryResult) -> JsonObject:
    return {
        "source_name": result.source_name,
        "answer": result.answer,
    }


_PUBLIC_ERRORS: tuple[
    tuple[type[MemCommitError], str, str, bool],
    ...,
] = (
    (QueryInputError, "invalid_request", "The Query request is invalid.", False),
    (
        QueryConfigurationError,
        "configuration_error",
        "The Query client configuration is invalid.",
        False,
    ),
    (
        QueryContextError,
        "context_unavailable",
        "The requested Query Context or Source is unavailable.",
        False,
    ),
    (
        QueryAuthorityError,
        "authority_denied",
        "The active Profile does not authorize this Query.",
        False,
    ),
    (
        QueryProviderFailure,
        "provider_failure",
        "The Query provider could not complete the request.",
        True,
    ),
    (
        QueryExecutionError,
        "execution_failed",
        "Authorized Query execution failed.",
        False,
    ),
    (
        QueryPublicationError,
        "publication_failed",
        "The Query answer was withheld because session publication failed.",
        False,
    ),
    (
        QueryStorageError,
        "storage_failure",
        "Query could not safely access local durable state.",
        False,
    ),
)


def _error_result(
    *,
    kind: QueryAgentKind | None,
    code: str,
    message: str,
    retryable: bool,
) -> JsonObject:
    return error_response(
        version=QUERY_AGENT_CONTRACT_VERSION,
        kind=kind,
        code=code,
        message=message,
        retryable=retryable,
    )


class QueryAgentAdapter:
    """Translate one versioned JSON payload to exactly one public Query call."""

    def __init__(self, client: MemCommitClient) -> None:
        if not isinstance(client, MemCommitClient):
            raise TypeError("QueryAgentAdapter requires a MemCommitClient.")
        self._client = client

    def invoke(self, payload: object) -> JsonObject:
        kind: QueryAgentKind | None = None
        if isinstance(payload, Mapping) and payload.get("kind") in {
            "ordinary",
            "granted",
            "reference",
        }:
            kind = payload["kind"]  # type: ignore[assignment]
        try:
            kind, arguments = _parse_request(payload)
        except _AgentRequestError as error:
            return _error_result(
                kind=kind,
                code="invalid_request",
                message=str(error),
                retryable=False,
            )

        try:
            if kind == "ordinary":
                result = self._client.query_ordinary(**arguments)  # type: ignore[arg-type]
                serialized = _ordinary_result(result)
            elif kind == "granted":
                result = self._client.query_granted(**arguments)  # type: ignore[arg-type]
                serialized = _granted_result(result)
            else:
                result = self._client.query_reference(**arguments)  # type: ignore[arg-type]
                serialized = _reference_result(result)
        except MemCommitError as error:
            for error_type, code, message, retryable in _PUBLIC_ERRORS:
                if isinstance(error, error_type):
                    return _error_result(
                        kind=kind,
                        code=code,
                        message=(
                            str(error)
                            if isinstance(
                                error,
                                (
                                    QueryInputError,
                                    QueryConfigurationError,
                                    QueryContextError,
                                    QueryAuthorityError,
                                ),
                            )
                            else message
                        ),
                        retryable=retryable,
                    )
            return _error_result(
                kind=kind,
                code="query_failed",
                message="Query failed without a more specific public category.",
                retryable=False,
            )
        except Exception:
            # Tool responses must not expose host paths, provider bodies, or
            # implementation exception text across the agent boundary.
            return _error_result(
                kind=kind,
                code="internal_error",
                message="The Query tool failed internally.",
                retryable=False,
            )

        return {
            "version": QUERY_AGENT_CONTRACT_VERSION,
            "ok": True,
            "kind": kind,
            "result": serialized,
        }


def query_agent_tool_schema() -> JsonObject:
    """Return a fresh function-tool schema for the versioned Query contract."""

    def text() -> JsonObject:
        return {"type": "string", "minLength": 1}

    reference = {
        "type": "object",
        "additionalProperties": False,
        "required": ["uid", "name", "target_source_uid", "provider"],
        "properties": {
            "uid": text(),
            "name": text(),
            "target_source_uid": text(),
            "provider": text(),
        },
    }
    base = {
        "version": {"type": "integer", "const": QUERY_AGENT_CONTRACT_VERSION},
    }
    parameters = {
        "type": "object",
        "oneOf": [
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["version", "kind", "question"],
                "properties": {
                    **base,
                    "kind": {"type": "string", "const": "ordinary"},
                    "question": text(),
                    "context_names": {
                        "type": "array",
                        "minItems": 1,
                        "uniqueItems": True,
                        "items": text(),
                    },
                    "include_descendants": {"type": "boolean", "default": False},
                    "follow_embeds": {"type": "boolean", "default": True},
                },
            },
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["version", "kind", "public_name"],
                "properties": {
                    **base,
                    "kind": {"type": "string", "const": "granted"},
                    "public_name": text(),
                    "question": {"type": ["string", "null"], "minLength": 1},
                    "language": {"type": "string", "minLength": 1, "default": "en"},
                    "session_name": {"type": ["string", "null"], "minLength": 1},
                    "memory_handle": {"type": ["string", "null"], "minLength": 1},
                    "federate_descendants": {"type": "boolean", "default": True},
                },
            },
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["version", "kind", "reference", "question"],
                "properties": {
                    **base,
                    "kind": {"type": "string", "const": "reference"},
                    "reference": reference,
                    "question": text(),
                    "language": {"type": "string", "minLength": 1, "default": "en"},
                },
            },
        ],
    }
    return {
        "name": QUERY_AGENT_TOOL_NAME,
        "description": (
            "Run one explicit MemCommit Query route through the same public "
            "Python facade used by embedding hosts."
        ),
        "parameters": parameters,
    }


__all__ = [
    "QUERY_AGENT_CONTRACT_VERSION",
    "QUERY_AGENT_ERROR_MESSAGE_LIMIT",
    "QUERY_AGENT_TOOL_NAME",
    "QueryAgentAdapter",
    "QueryAgentKind",
    "query_agent_tool_schema",
]
