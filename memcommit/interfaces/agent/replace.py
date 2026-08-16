"""Versioned agent adapter for deterministic Replace review and Apply."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from memcommit.api import (
    MemCommitClient,
    ReplaceConflictError,
    ReplaceContextError,
    ReplaceError,
    ReplaceExecutionError,
    ReplaceInputError,
    ReplaceStorageError,
)
from memcommit.interfaces.agent.contract import (
    AgentRequestError,
    JsonObject,
    error_response,
    exact_fields,
    object_value,
    text_value,
)


REPLACE_AGENT_CONTRACT_VERSION = 1
REPLACE_AGENT_TOOL_NAME = "memcommit_replace"
ReplaceAgentKind = Literal["plan", "apply"]


def _parse_request(payload: object):
    value = object_value(payload, label="Replace request")
    version = value.get("version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != REPLACE_AGENT_CONTRACT_VERSION
    ):
        raise AgentRequestError(
            f"version must be exactly {REPLACE_AGENT_CONTRACT_VERSION}."
        )
    kind = value.get("kind")
    if kind not in {"plan", "apply"}:
        raise AgentRequestError("kind must be plan or apply.")
    exact_fields(
        value,
        required={"version", "kind", "pattern", "replacement"},
        optional=frozenset(
            {
                "context_names",
                "include_descendants",
                "follow_embeds",
                "regex",
                "ignore_case",
                "expected_plan_digest",
            }
        ),
        label="Replace request",
    )
    expected = value.get("expected_plan_digest")
    if kind == "apply":
        if (
            not isinstance(expected, str)
            or len(expected) != 64
            or any(character not in "0123456789abcdef" for character in expected)
        ):
            raise AgentRequestError(
                "apply requires a 64-character lowercase expected_plan_digest."
            )
    elif expected is not None:
        raise AgentRequestError("plan must not include expected_plan_digest.")
    names_value = value.get("context_names", [])
    if not isinstance(names_value, list) or any(
        not isinstance(name, str) or not name.strip() for name in names_value
    ):
        raise AgentRequestError("context_names must be an array of nonblank strings.")
    names = tuple(names_value)
    if len(set(names)) != len(names):
        raise AgentRequestError("context_names must not repeat.")
    fields = (
        "include_descendants",
        "follow_embeds",
        "regex",
        "ignore_case",
    )
    flags = tuple(value.get(field, False) for field in fields)
    if any(type(flag) is not bool for flag in flags):
        raise AgentRequestError("Replace mode and reach fields must be booleans.")
    replacement = value.get("replacement")
    if not isinstance(replacement, str):
        raise AgentRequestError("replacement must be text and may be empty.")
    return (
        kind,
        text_value(value.get("pattern"), field="pattern"),
        replacement,
        names,
        *flags,
        expected,
    )


def _plan(result) -> JsonObject:
    return {
        "pattern": result.pattern,
        "replacement": result.replacement,
        "context_names": list(result.context_names),
        "include_descendants": result.include_descendants,
        "follow_embeds": result.follow_embeds,
        "mode": result.mode,
        "ignore_case": result.ignore_case,
        "plan_digest": result.plan_digest,
        "scanned_context_count": result.scanned_context_count,
        "scanned_memory_count": result.scanned_memory_count,
        "matched_memory_count": result.matched_memory_count,
        "changed_memory_count": result.changed_memory_count,
        "occurrence_count": result.occurrence_count,
        "contexts": [
            {
                "context_name": context.context_name,
                "context_uid": context.context_uid,
                "context_digest": context.context_digest,
                "scanned_memory_count": context.scanned_memory_count,
                "matches": [
                    {
                        "memory_uid": match.memory_uid,
                        "before_content": match.before_content,
                        "after_content": match.after_content,
                        "changed": match.changed,
                        "spans": [
                            {"start": span.start, "end": span.end, "text": span.text}
                            for span in match.spans
                        ],
                    }
                    for match in context.matches
                ],
            }
            for context in result.contexts
        ],
        "effect": "NONE",
        "provider_used": False,
    }


def _applied(result) -> JsonObject:
    return {
        "plan_digest": result.plan_digest,
        "applied": result.applied,
        "scanned_context_count": result.scanned_context_count,
        "scanned_memory_count": result.scanned_memory_count,
        "matched_memory_count": result.matched_memory_count,
        "changed_memory_count": result.changed_memory_count,
        "occurrence_count": result.occurrence_count,
        "checkpoints": [
            {
                "context_name": checkpoint.context_name,
                "context_uid": checkpoint.context_uid,
                "checkpoint_uid": checkpoint.checkpoint_uid,
            }
            for checkpoint in result.checkpoints
        ],
        "effect": "CONTEXTS_CHANGED" if result.applied else "NONE",
        "provider_used": False,
    }


_PUBLIC_ERRORS: tuple[tuple[type[ReplaceError], str, str], ...] = (
    (ReplaceInputError, "invalid_request", "The Replace request is invalid."),
    (ReplaceContextError, "context_unavailable", "A Replace Context is unavailable."),
    (ReplaceConflictError, "stale_plan", "The reviewed Replace plan is stale."),
    (ReplaceStorageError, "storage_failure", "Replace could not safely use the Store."),
    (
        ReplaceExecutionError,
        "execution_failed",
        "Replace did not publish a complete atomic result.",
    ),
)


class ReplaceAgentAdapter:
    def __init__(self, client: MemCommitClient) -> None:
        if not isinstance(client, MemCommitClient):
            raise TypeError("ReplaceAgentAdapter requires a MemCommitClient.")
        self._client = client

    def invoke(self, payload: object) -> JsonObject:
        kind: ReplaceAgentKind | None = None
        if isinstance(payload, Mapping) and payload.get("kind") in {"plan", "apply"}:
            kind = payload["kind"]
        try:
            (
                kind,
                pattern,
                replacement,
                names,
                descendants,
                embeds,
                regex,
                ignore_case,
                expected,
            ) = _parse_request(payload)
        except AgentRequestError as error:
            return error_response(
                version=REPLACE_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="invalid_request",
                message=str(error),
                retryable=False,
            )
        try:
            plan = self._client.plan_replace(
                pattern,
                replacement,
                names,
                include_descendants=descendants,
                follow_embeds=embeds,
                regex=regex,
                ignore_case=ignore_case,
            )
            if kind == "plan":
                result = _plan(plan)
            else:
                assert isinstance(expected, str)
                if plan.plan_digest != expected:
                    raise ReplaceConflictError(
                        "The current Replace plan does not match expected_plan_digest."
                    )
                result = _applied(self._client.apply_replace(plan))
        except ReplaceError as error:
            for error_type, code, message in _PUBLIC_ERRORS:
                if isinstance(error, error_type):
                    return error_response(
                        version=REPLACE_AGENT_CONTRACT_VERSION,
                        kind=kind,
                        code=code,
                        message=(
                            str(error)
                            if isinstance(
                                error,
                                (ReplaceInputError, ReplaceContextError, ReplaceConflictError),
                            )
                            else message
                        ),
                        retryable=isinstance(error, ReplaceConflictError),
                    )
            return error_response(
                version=REPLACE_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="replace_failed",
                message="Replace failed without a more specific public category.",
                retryable=False,
            )
        except Exception:
            return error_response(
                version=REPLACE_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="internal_error",
                message="The Replace tool failed internally.",
                retryable=False,
            )
        return {
            "version": REPLACE_AGENT_CONTRACT_VERSION,
            "ok": True,
            "kind": kind,
            "result": result,
        }


def replace_agent_tool_schema() -> JsonObject:
    return {
        "name": REPLACE_AGENT_TOOL_NAME,
        "description": (
            "Plan or apply deterministic literal/explicit-regex replacement in "
            "ordinary local Contexts. Apply requires the exact digest returned "
            "by a prior plan and publishes one atomic Undo/Redo command unit."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["version", "kind", "pattern", "replacement"],
            "properties": {
                "version": {"type": "integer", "const": 1},
                "kind": {"type": "string", "enum": ["plan", "apply"]},
                "pattern": {"type": "string", "minLength": 1, "maxLength": 2000},
                "replacement": {"type": "string"},
                "context_names": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1, "pattern": r".*\S.*"},
                    "uniqueItems": True,
                    "default": [],
                },
                "include_descendants": {"type": "boolean", "default": False},
                "follow_embeds": {"type": "boolean", "default": False},
                "regex": {"type": "boolean", "default": False},
                "ignore_case": {"type": "boolean", "default": False},
                "expected_plan_digest": {
                    "type": "string",
                    "pattern": "^[0-9a-f]{64}$",
                },
            },
            "allOf": [
                {
                    "if": {"properties": {"kind": {"const": "apply"}}},
                    "then": {"required": ["expected_plan_digest"]},
                    "else": {"not": {"required": ["expected_plan_digest"]}},
                }
            ],
        },
    }


__all__ = [
    "REPLACE_AGENT_CONTRACT_VERSION",
    "REPLACE_AGENT_TOOL_NAME",
    "ReplaceAgentAdapter",
    "ReplaceAgentKind",
    "replace_agent_tool_schema",
]
