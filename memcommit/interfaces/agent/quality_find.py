"""Versioned JSON-safe agent adapter for read-only quality finders."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

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
from memcommit.semantic_redundancy_evidence import (
    REDUNDANCY_EVIDENCE_VERSION,
    redundancy_evidence_dict,
)


QUALITY_FIND_AGENT_CONTRACT_VERSION = 1
QUALITY_FIND_AGENT_TOOL_NAME = "memcommit_quality_find"


def quality_finding_handoff_agent_schema() -> JsonObject:
    """Return the strict nested receipt schema shared with Resolve."""

    text = {"type": "string", "minLength": 1}
    nullable_text = {"type": ["string", "null"], "minLength": 1}
    string_array = {"type": "array", "items": text}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "contract",
            "uid",
            "finding_uid",
            "kind",
            "route",
            "source_frame_digest",
            "sources",
            "memory_uids",
            "memory_context_names",
            "classification",
            "qualifiers",
            "reason",
            "question",
            "proposed_readings",
            "review_draft",
        ],
        "properties": {
            "contract": {"type": "string", "const": "quality-finding-handoff-v1"},
            "uid": text,
            "finding_uid": text,
            "kind": {
                "type": "string",
                "enum": ["DUPLICATE", "AMBIGUITY", "CONFLICT"],
            },
            "route": {
                "type": "string",
                "enum": ["DEDUP", "CLARIFY", "RESOLVE"],
            },
            "source_frame_digest": text,
            "sources": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "context_uid",
                        "display_name",
                        "direct_memory_digest",
                    ],
                    "properties": {
                        "context_uid": text,
                        "display_name": text,
                        "direct_memory_digest": text,
                    },
                },
            },
            "memory_uids": string_array,
            "memory_context_names": string_array,
            "classification": text,
            "qualifiers": string_array,
            "reason": text,
            "question": {"type": "string"},
            "proposed_readings": string_array,
            "review_draft": {
                "type": "object",
                "additionalProperties": False,
                "required": ["selected_option_uid", "text"],
                "properties": {
                    "selected_option_uid": nullable_text,
                    "text": {"type": "string"},
                },
            },
        },
    }


def redundancy_evidence_agent_schema() -> JsonObject:
    """Return the strict public evidence schema accepted by Dedun."""

    schema = deepcopy(quality_finding_handoff_agent_schema())
    properties = schema["properties"]
    assert isinstance(properties, dict)
    properties["contract"] = {
        "type": "string",
        "const": REDUNDANCY_EVIDENCE_VERSION,
    }
    properties["kind"] = {"type": "string", "const": "REDUNDANCY"}
    properties["route"] = {"type": "string", "const": "DEDUN"}
    properties["classification"] = {
        "type": "string",
        "enum": ["EXACT", "SURFACE_EQUIVALENT", "SEMANTIC_EQUIVALENT"],
    }
    return schema


def _parse_request(payload: object) -> tuple[str, tuple[str, ...]]:
    value = object_value(payload, label="Quality Find request")
    exact_fields(
        value,
        required={"version", "kind"},
        optional={"context_names"},
        label="Quality Find request",
    )
    version = value["version"]
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != QUALITY_FIND_AGENT_CONTRACT_VERSION
    ):
        raise AgentRequestError(
            f"version must be exactly {QUALITY_FIND_AGENT_CONTRACT_VERSION}."
        )
    kind = text_value(value["kind"], field="kind")
    if kind not in {"redundancies", "ambiguities", "conflicts"}:
        raise AgentRequestError("kind must be redundancies, ambiguities, or conflicts.")
    raw_names = value.get("context_names", [])
    if not isinstance(raw_names, list):
        raise AgentRequestError("context_names must be an array.")
    names = tuple(
        text_value(item, field=f"context_names[{index}]")
        for index, item in enumerate(raw_names)
    )
    if len(set(names)) != len(names):
        raise AgentRequestError("context_names must not repeat.")
    return kind, names


_PUBLIC_ERRORS: tuple[tuple[type[SemanticError], str, str, bool], ...] = (
    (SemanticInputError, "invalid_request", "The finder request is invalid.", False),
    (
        SemanticContextError,
        "context_unavailable",
        "A finder Context is unavailable.",
        False,
    ),
    (
        SemanticAuthorityError,
        "authority_denied",
        "Quality finder authority was denied.",
        False,
    ),
    (
        SemanticProviderFailure,
        "provider_failure",
        "The quality finder provider failed.",
        True,
    ),
    (
        SemanticStorageError,
        "storage_failure",
        "Quality finder storage failed safely.",
        False,
    ),
    (
        SemanticExecutionError,
        "execution_failed",
        "Quality finder execution failed.",
        False,
    ),
)


class QualityFindAgentAdapter:
    """Expose all three read-only finders through one typed result contract."""

    def __init__(self, client: MemCommitClient) -> None:
        if not isinstance(client, MemCommitClient):
            raise TypeError("QualityFindAgentAdapter requires a MemCommitClient.")
        self._client = client

    def invoke(self, payload: object) -> JsonObject:
        kind: str | None = None
        if isinstance(payload, Mapping) and isinstance(payload.get("kind"), str):
            kind = payload["kind"]
        try:
            kind, context_names = _parse_request(payload)
        except AgentRequestError as error:
            return error_response(
                version=QUALITY_FIND_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="invalid_request",
                message=str(error),
                retryable=False,
            )
        try:
            operation = {
                "redundancies": self._client.find_redundancies,
                "ambiguities": self._client.find_ambiguities,
                "conflicts": self._client.find_conflicts,
            }[kind]
            result = operation(context_names)
        except SemanticError as error:
            for error_type, code, message, retryable in _PUBLIC_ERRORS:
                if isinstance(error, error_type):
                    return error_response(
                        version=QUALITY_FIND_AGENT_CONTRACT_VERSION,
                        kind=kind,
                        code=code,
                        message=(
                            str(error)
                            if isinstance(
                                error,
                                (
                                    SemanticInputError,
                                    SemanticContextError,
                                    SemanticAuthorityError,
                                ),
                            )
                            else message
                        ),
                        retryable=retryable,
                    )
            return error_response(
                version=QUALITY_FIND_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="find_failed",
                message="Quality Find failed without a public category.",
                retryable=False,
            )
        except Exception:
            return error_response(
                version=QUALITY_FIND_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="internal_error",
                message="The Quality Find tool failed internally.",
                retryable=False,
            )
        return {
            "version": QUALITY_FIND_AGENT_CONTRACT_VERSION,
            "ok": True,
            "kind": kind,
            "result": {
                "context_names": list(result.context_names),
                "source_digest": result.source_digest,
                "memory_count": result.memory_count,
                "pair_count": result.pair_count,
                "evidence": [
                    (
                        redundancy_evidence_dict(handoff)
                        if kind == "redundancies"
                        else handoff.to_dict()
                    )
                    for handoff in result.evidence
                ],
                "exact_item_groups": [
                    {
                        "item_kind": group.item_kind,
                        "survivor_uid": group.survivor_uid,
                        "absorbed_uids": list(group.absorbed_uids),
                        "summary": group.summary,
                    }
                    for group in result.exact_item_groups
                ],
                "effect": "NONE",
            },
        }


def quality_find_agent_tool_schema() -> JsonObject:
    """Return the strict read-only quality finder schema."""

    return {
        "name": QUALITY_FIND_AGENT_TOOL_NAME,
        "description": (
            "Find complete exact-plus-semantic redundancies, ambiguities, or "
            "conflicts in one frozen readable Context frame. Returns typed "
            "evidence and never mutates a Context."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["version", "kind"],
            "properties": {
                "version": {
                    "type": "integer",
                    "const": QUALITY_FIND_AGENT_CONTRACT_VERSION,
                },
                "kind": {
                    "type": "string",
                    "enum": ["redundancies", "ambiguities", "conflicts"],
                },
                "context_names": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                },
            },
        },
    }


__all__ = [
    "QUALITY_FIND_AGENT_CONTRACT_VERSION",
    "QUALITY_FIND_AGENT_TOOL_NAME",
    "QualityFindAgentAdapter",
    "quality_find_agent_tool_schema",
    "quality_finding_handoff_agent_schema",
    "redundancy_evidence_agent_schema",
    "semantic_redundancy_evidence_agent_schema",
]


# Compatibility export for plugins compiled against the v1 semantic-only name.
semantic_redundancy_evidence_agent_schema = redundancy_evidence_agent_schema
