"""Versioned JSON-safe agent adapter for structural Atomize."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from memcommit.api import (
    AtomizeAnalysisResult,
    AtomizeConflictError,
    AtomizeContextError,
    AtomizeError,
    AtomizeExecutionError,
    AtomizeInputError,
    AtomizeProviderFailure,
    AtomizeStorageError,
    AtomizeStructuralApplyResult,
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


ATOMIZE_AGENT_CONTRACT_VERSION = 1
ATOMIZE_AGENT_TOOL_NAME = "memcommit_atomize"
AtomizeAgentKind = Literal["open", "apply_as_is"]


def _boolean(value: object, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise AgentRequestError(f"{field} must be a boolean.")
    return value


def _kind(value: Mapping[str, object]) -> AtomizeAgentKind:
    version = value.get("version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != ATOMIZE_AGENT_CONTRACT_VERSION
    ):
        raise AgentRequestError(
            f"version must be exactly {ATOMIZE_AGENT_CONTRACT_VERSION}."
        )
    kind = value.get("kind")
    if kind not in {"open", "apply_as_is"}:
        raise AgentRequestError("kind must be one of: open, apply_as_is.")
    return kind  # type: ignore[return-value]


def _context_name(value: Mapping[str, object]) -> str | None:
    return text_value(
        value.get("context_name"),
        field="context_name",
        optional=True,
    )


def _expected_version(value: object) -> str:
    version = text_value(value, field="expected_version")
    if len(version) != 64 or any(
        character not in "0123456789abcdef" for character in version
    ):
        raise AgentRequestError(
            "expected_version must be a 64-character lowercase hexadecimal token."
        )
    return version


def _parse_request(payload: object) -> tuple[AtomizeAgentKind, dict[str, object]]:
    value = object_value(payload, label="Atomize request")
    kind = _kind(value)
    if kind == "open":
        exact_fields(
            value,
            required={"version", "kind"},
            optional=frozenset({"context_name", "refresh", "use_prepared"}),
            label="Atomize open request",
        )
        return kind, {
            "context_name": _context_name(value),
            "refresh": _boolean(value.get("refresh", False), field="refresh"),
            "use_prepared": _boolean(
                value.get("use_prepared", True),
                field="use_prepared",
            ),
        }
    exact_fields(
        value,
        required={"version", "kind", "expected_version"},
        optional=frozenset({"context_name"}),
        label="Atomize apply_as_is request",
    )
    return kind, {
        "context_name": _context_name(value),
        "expected_version": _expected_version(value["expected_version"]),
    }


def _analysis_result(result: AtomizeAnalysisResult) -> JsonObject:
    provider_used = result.origin == "PROVIDER"
    cache_used = result.origin in {"SAVED", "EXACT_PREWARM"}
    return {
        "analysis_uid": result.analysis_uid,
        "version": result.version,
        "origin": result.origin,
        "provider_used": provider_used,
        "cache_used": cache_used,
        "effect": "NONE" if result.origin == "SAVED" else "DERIVED_SESSION",
        "context_uid": result.context_uid,
        "context_name": result.context_name,
        "context_digest": result.context_digest,
        "ruleset_version": result.ruleset_version,
        "memory_count": result.memory_count,
        "projected_memory_count": result.projected_memory_count,
        "overview": {
            "understood": {
                "text": result.overview.understood.text,
                "source_memory_uids": list(
                    result.overview.understood.source_memory_uids
                ),
            },
            "changed": {
                "text": result.overview.changed.text,
                "source_memory_uids": list(
                    result.overview.changed.source_memory_uids
                ),
            },
            "unresolved": {
                "text": result.overview.unresolved.text,
                "source_memory_uids": list(
                    result.overview.unresolved.source_memory_uids
                ),
            },
        },
        "items": [
            {
                "memory_uid": item.memory_uid,
                "content": item.content,
                "position": item.position,
                "classification": item.classification,
                "action": item.action,
                "reason_codes": list(item.reason_codes),
                "children": [
                    {
                        "content": child.content,
                        "source_spans": list(child.source_spans),
                        "frame_spans": list(child.frame_spans),
                    }
                    for child in item.children
                ],
                "reason": item.reason,
                "lint": list(item.lint),
            }
            for item in result.items
        ],
        "issues": [
            {
                "uid": issue.uid,
                "kind": issue.kind,
                "source_memory_uids": list(issue.source_memory_uids),
                "priority": issue.priority,
                "classification": issue.classification,
                "reason": issue.reason,
                "question": issue.question,
                "readings": [
                    {
                        "uid": reading.uid,
                        "role": reading.role,
                        "label": reading.label,
                        "text": reading.text,
                    }
                    for reading in issue.readings
                ],
                "answered": issue.answered,
            }
            for issue in result.issues
        ],
        "workbench_uid": result.workbench_uid,
        "output_context_name": result.output_context_name,
        "in_place_apply_allowed": result.in_place_apply_allowed,
        "apply_as_is": {
            "allowed": result.in_place_apply_allowed,
            "expected_version": result.version,
            "provider_used": False,
            "effect": "CONTEXT_CHECKPOINT",
        },
    }


def _apply_result(result: AtomizeStructuralApplyResult) -> JsonObject:
    return {
        "analysis_uid": result.analysis_uid,
        "context_uid": result.context_uid,
        "context_name": result.context_name,
        "checkpoint_uid": result.checkpoint_uid,
        "split_count": result.split_count,
        "child_count": result.child_count,
        "preserved_count": result.preserved_count,
        "application_mode": result.application_mode,
        "unresolved_at_apply_count": result.unresolved_at_apply_count,
        "items": [
            {
                "source_memory_uid": item.source_memory_uid,
                "classification": item.classification,
                "result_memory_uids": list(item.result_memory_uids),
                "result_contents": list(item.result_contents),
                "reason": item.reason,
                "reason_codes": list(item.reason_codes),
            }
            for item in result.items
        ],
        "recovered": result.recovered,
        "provider_used": False,
        "effect": "CONTEXT_CHECKPOINT",
    }


_PUBLIC_ERRORS: tuple[tuple[type[AtomizeError], str, str, bool], ...] = (
    (AtomizeInputError, "invalid_request", "The Atomize request is invalid.", False),
    (
        AtomizeContextError,
        "context_unavailable",
        "The Atomize Context or saved analysis is unavailable.",
        False,
    ),
    (
        AtomizeProviderFailure,
        "provider_failure",
        "The Atomize provider failed.",
        True,
    ),
    (
        AtomizeConflictError,
        "stale_state",
        "The accepted Atomize revision changed.",
        False,
    ),
    (
        AtomizeStorageError,
        "storage_failure",
        "Atomize storage failed safely.",
        False,
    ),
    (
        AtomizeExecutionError,
        "execution_failed",
        "Atomize failed before publishing a complete outcome.",
        False,
    ),
)


class AtomizeAgentAdapter:
    """Translate one exact JSON action to one public structural call."""

    def __init__(self, client: MemCommitClient) -> None:
        if not isinstance(client, MemCommitClient):
            raise TypeError("AtomizeAgentAdapter requires a MemCommitClient.")
        self._client = client

    def invoke(self, payload: object) -> JsonObject:
        kind: AtomizeAgentKind | None = None
        if isinstance(payload, Mapping) and payload.get("kind") in {
            "open",
            "apply_as_is",
        }:
            kind = payload["kind"]  # type: ignore[assignment]
        try:
            kind, arguments = _parse_request(payload)
        except AgentRequestError as error:
            return error_response(
                version=ATOMIZE_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="invalid_request",
                message=str(error),
                retryable=False,
            )

        try:
            if kind == "open":
                result = self._client.open_atomize_analysis(**arguments)
                projected = _analysis_result(result)
            else:
                result = self._client.apply_saved_atomize_as_is(**arguments)
                projected = _apply_result(result)
        except AtomizeError as error:
            for error_type, code, message, retryable in _PUBLIC_ERRORS:
                if isinstance(error, error_type):
                    return error_response(
                        version=ATOMIZE_AGENT_CONTRACT_VERSION,
                        kind=kind,
                        code=code,
                        message=(
                            str(error)
                            if isinstance(error, (AtomizeInputError, AtomizeContextError))
                            else message
                        ),
                        retryable=retryable,
                    )
            return error_response(
                version=ATOMIZE_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="atomize_failed",
                message="Atomize failed without a more specific public category.",
                retryable=False,
            )
        except Exception:
            return error_response(
                version=ATOMIZE_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="internal_error",
                message="The Atomize tool failed internally.",
                retryable=False,
            )

        return {
            "version": ATOMIZE_AGENT_CONTRACT_VERSION,
            "ok": True,
            "kind": kind,
            "result": projected,
        }


def atomize_agent_tool_schema() -> JsonObject:
    """Return the strict structural review and exact-Apply schema."""

    text = {"type": "string", "minLength": 1, "pattern": r".*\S.*"}
    nullable_text = {**text, "type": ["string", "null"]}
    version = {"type": "integer", "const": ATOMIZE_AGENT_CONTRACT_VERSION}
    open_request: JsonObject = {
        "type": "object",
        "additionalProperties": False,
        "required": ["version", "kind"],
        "properties": {
            "version": version,
            "kind": {"type": "string", "const": "open"},
            "context_name": nullable_text,
            "refresh": {
                "type": "boolean",
                "default": False,
                "description": "Force a new provider analysis instead of saved reuse.",
            },
            "use_prepared": {
                "type": "boolean",
                "default": True,
                "description": "Allow an exact hidden prepared analysis when available.",
            },
        },
    }
    apply_request: JsonObject = {
        "type": "object",
        "additionalProperties": False,
        "required": ["version", "kind", "expected_version"],
        "properties": {
            "version": version,
            "kind": {"type": "string", "const": "apply_as_is"},
            "context_name": nullable_text,
            "expected_version": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$",
                "description": "Opaque version returned by the reviewed open action.",
            },
        },
    }
    return {
        "name": ATOMIZE_AGENT_TOOL_NAME,
        "description": (
            "Open one complete structural Atomize review, then optionally apply "
            "that exact revision in place. Open reports provider/cache use and may "
            "create or reuse a derived review session; apply_as_is never calls the "
            "provider and mutates the local Context through one checkpoint. Save As "
            "and response editing are not exposed by this tool."
        ),
        "parameters": {
            "type": "object",
            "oneOf": [open_request, apply_request],
        },
    }


__all__ = [
    "ATOMIZE_AGENT_CONTRACT_VERSION",
    "ATOMIZE_AGENT_TOOL_NAME",
    "AtomizeAgentAdapter",
    "AtomizeAgentKind",
    "atomize_agent_tool_schema",
]
