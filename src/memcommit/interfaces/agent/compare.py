"""Versioned JSON-safe agent adapter for read-only Compare analyses."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from memcommit.adapters.python_api import (
    CompareAuthorityError,
    CompareConflictError,
    CompareContextError,
    CompareError,
    CompareExecutionError,
    CompareInputError,
    CompareProviderFailure,
    CompareStorageError,
    ComparisonResult,
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


COMPARE_AGENT_CONTRACT_VERSION = 1
COMPARE_AGENT_TOOL_NAME = "memcommit_compare"
CompareAgentKind = Literal["run", "open", "refresh"]


def _boolean(value: object, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise AgentRequestError(f"{field} must be a boolean.")
    return value


def _parse_request(payload: object) -> tuple[CompareAgentKind, dict[str, object]]:
    value = object_value(payload, label="Compare request")
    version = value.get("version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != COMPARE_AGENT_CONTRACT_VERSION
    ):
        raise AgentRequestError(
            f"version must be exactly {COMPARE_AGENT_CONTRACT_VERSION}."
        )
    kind = value.get("kind")
    if kind not in {"run", "open", "refresh"}:
        raise AgentRequestError("kind must be one of: run, open, refresh.")
    if kind == "run":
        exact_fields(
            value,
            required={
                "version",
                "kind",
                "reference_context",
                "compared_context",
            },
            optional=frozenset(
                {
                    "reference_descendants",
                    "compared_descendants",
                    "reference_memory",
                    "compared_memory",
                }
            ),
            label="Compare run request",
        )
        return kind, {
            "reference_context": text_value(
                value["reference_context"],
                field="reference_context",
            ),
            "compared_context": text_value(
                value["compared_context"],
                field="compared_context",
            ),
            "reference_descendants": _boolean(
                value.get("reference_descendants", False),
                field="reference_descendants",
            ),
            "compared_descendants": _boolean(
                value.get("compared_descendants", False),
                field="compared_descendants",
            ),
            "reference_memory": text_value(
                value.get("reference_memory"),
                field="reference_memory",
                optional=True,
            ),
            "compared_memory": text_value(
                value.get("compared_memory"),
                field="compared_memory",
                optional=True,
            ),
        }
    required = {"version", "kind", "analysis_uid"}
    if kind == "refresh":
        required.add("expected_version")
    exact_fields(
        value,
        required=required,
        label=f"Compare {kind} request",
    )
    arguments = {
        "analysis_uid": text_value(value["analysis_uid"], field="analysis_uid")
    }
    if kind == "refresh":
        arguments["expected_version"] = text_value(
            value["expected_version"],
            field="expected_version",
        )
    return kind, arguments


def _result(result: ComparisonResult, *, kind: CompareAgentKind) -> JsonObject:
    return {
        "analysis_uid": result.analysis_uid,
        "version": result.version,
        "ruleset_version": result.ruleset_version,
        "frames": [
            {
                "uid": frame.uid,
                "side": frame.side,
                "context_name": frame.context_name,
                "memory_uids": list(frame.memory_uids),
                "selected_memory_uid": frame.selected_memory_uid,
            }
            for frame in result.frames
        ],
        "include_descendants": list(result.include_descendants),
        "overview": result.overview,
        "reports": (
            {
                "both": result.reports.both,
                "differences": result.reports.differences,
                "reference_only": result.reports.reference_only,
                "compared_only": result.reports.compared_only,
            }
            if result.reports is not None
            else None
        ),
        "relations": [
            {
                "uid": relation.uid,
                "kind": relation.kind,
                "status": relation.status,
                "members": [
                    {
                        "frame_uid": member.frame_uid,
                        "memory_uid": member.memory_uid,
                    }
                    for member in relation.members
                ],
                "summary": relation.summary,
                "reason": relation.reason,
            }
            for relation in result.relations
        ],
        "issues": [
            {
                "uid": issue.uid,
                "relation_uids": list(issue.relation_uids),
                "priority": issue.priority,
                "title": issue.title,
                "question": issue.question,
                "why_it_matters": issue.why_it_matters,
                "options": [
                    {
                        "uid": option.uid,
                        "label": option.label,
                        "text": option.text,
                    }
                    for option in issue.options
                ],
            }
            for issue in result.issues
        ],
        "origin": result.origin,
        "durable": result.durable,
        "retention": result.retention,
        "effect": (
            "COMPARE_ANALYSIS_SLOT"
            if result.durable
            and kind != "open"
            and result.origin not in {"SAVED_REUSE", "SAVED_OPEN"}
            else "NONE"
        ),
    }


_PUBLIC_ERRORS: tuple[tuple[type[CompareError], str, str, bool], ...] = (
    (CompareInputError, "invalid_request", "The Compare request is invalid.", False),
    (
        CompareContextError,
        "context_unavailable",
        "A Compare Context or analysis is unavailable.",
        False,
    ),
    (CompareAuthorityError, "authority_denied", "Compare authority was denied.", False),
    (CompareProviderFailure, "provider_failure", "The Compare provider failed.", True),
    (CompareConflictError, "concurrent_update", "The Compare changed concurrently.", False),
    (CompareStorageError, "storage_failure", "Compare storage failed safely.", False),
    (CompareExecutionError, "execution_failed", "Compare execution failed.", False),
)


class CompareAgentAdapter:
    """Translate one exact JSON action to the public Compare facade."""

    def __init__(self, client: MemCommitClient) -> None:
        if not isinstance(client, MemCommitClient):
            raise TypeError("CompareAgentAdapter requires a MemCommitClient.")
        self._client = client

    def invoke(self, payload: object) -> JsonObject:
        kind: CompareAgentKind | None = None
        if isinstance(payload, Mapping) and payload.get("kind") in {
            "run",
            "open",
            "refresh",
        }:
            kind = payload["kind"]  # type: ignore[assignment]
        try:
            kind, arguments = _parse_request(payload)
        except AgentRequestError as error:
            return error_response(
                version=COMPARE_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="invalid_request",
                message=str(error),
                retryable=False,
            )
        try:
            method_name = "compare_contexts" if kind == "run" else f"{kind}_comparison"
            result = getattr(self._client, method_name)(**arguments)
        except CompareError as error:
            for error_type, code, message, retryable in _PUBLIC_ERRORS:
                if isinstance(error, error_type):
                    return error_response(
                        version=COMPARE_AGENT_CONTRACT_VERSION,
                        kind=kind,
                        code=code,
                        message=(
                            str(error)
                            if isinstance(
                                error,
                                (CompareInputError, CompareContextError),
                            )
                            else message
                        ),
                        retryable=retryable,
                    )
            return error_response(
                version=COMPARE_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="compare_failed",
                message="Compare failed without a more specific public category.",
                retryable=False,
            )
        except Exception:
            return error_response(
                version=COMPARE_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="internal_error",
                message="The Compare tool failed internally.",
                retryable=False,
            )
        return {
            "version": COMPARE_AGENT_CONTRACT_VERSION,
            "ok": True,
            "kind": kind,
            "result": _result(result, kind=kind),
        }


def compare_agent_tool_schema() -> JsonObject:
    text = {"type": "string", "minLength": 1, "pattern": r".*\S.*"}
    return {
        "name": COMPARE_AGENT_TOOL_NAME,
        "description": (
            "Run or open one complete ordered peer-Context Compare. Compare is "
            "read-only with respect to its Contexts; refresh replaces only the "
            "exact reviewed analysis slot and requires the version returned by open."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["version", "kind"],
            "properties": {
                "version": {
                    "type": "integer",
                    "const": COMPARE_AGENT_CONTRACT_VERSION,
                },
                "kind": {
                    "type": "string",
                    "enum": ["run", "open", "refresh"],
                },
                "reference_context": text,
                "compared_context": text,
                "reference_descendants": {"type": "boolean", "default": False},
                "compared_descendants": {"type": "boolean", "default": False},
                "reference_memory": {**text, "type": ["string", "null"]},
                "compared_memory": {**text, "type": ["string", "null"]},
                "analysis_uid": text,
                "expected_version": {
                    **text,
                    "description": (
                        "Opaque version returned by open; required only for refresh."
                    ),
                },
            },
        },
    }


__all__ = [
    "COMPARE_AGENT_CONTRACT_VERSION",
    "COMPARE_AGENT_TOOL_NAME",
    "CompareAgentAdapter",
    "CompareAgentKind",
    "compare_agent_tool_schema",
]
