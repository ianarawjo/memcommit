"""Versioned read-only agent adapter for operation discovery."""

from __future__ import annotations

from typing import Literal

from memcommit.adapters.python_api import (
    HelpComparisonResult,
    HelpDetailReferenceResult,
    HelpDetailResult,
    HelpInputError,
    HelpTextDetailResult,
    MemCommitClient,
    OperationHelpResult,
)
from memcommit.application.operations.help.application import (
    list_operation_details,
    list_operation_help,
)
from memcommit.adapters.agent.contract import (
    AgentRequestError,
    JsonObject,
    error_response,
    exact_fields,
    object_value,
    text_value,
)


HELP_AGENT_CONTRACT_VERSION = 1
HELP_AGENT_TOOL_NAME = "memcommit_help"
HelpAgentKind = Literal["list", "describe", "list-details", "describe-detail"]


def _parse_request(
    payload: object,
) -> tuple[HelpAgentKind, str | None, str | None]:
    value = object_value(payload, label="Help request")
    version = value.get("version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != HELP_AGENT_CONTRACT_VERSION
    ):
        raise AgentRequestError(
            f"version must be exactly {HELP_AGENT_CONTRACT_VERSION}."
        )
    kind = value.get("kind")
    if kind == "list":
        exact_fields(value, required={"version", "kind"}, label="Help list request")
        return "list", None, None
    if kind == "describe":
        exact_fields(
            value,
            required={"version", "kind", "operation"},
            label="Help describe request",
        )
        return "describe", text_value(value["operation"], field="operation"), None
    if kind == "list-details":
        exact_fields(
            value,
            required={"version", "kind", "operation"},
            label="Help detail-list request",
        )
        return (
            "list-details",
            text_value(value["operation"], field="operation"),
            None,
        )
    if kind == "describe-detail":
        exact_fields(
            value,
            required={"version", "kind", "operation", "detail"},
            label="Help detail request",
        )
        return (
            "describe-detail",
            text_value(value["operation"], field="operation"),
            text_value(value["detail"], field="detail"),
        )
    raise AgentRequestError(
        "kind must be one of: list, describe, list-details, describe-detail."
    )


def _detail_reference(result: HelpDetailReferenceResult) -> JsonObject:
    return {
        "id": result.id,
        "operation": result.operation,
        "kind": result.kind,
        "title": result.title,
        "use_when": result.use_when,
        "discovery": result.discovery,
        "discovery_summary": result.discovery_summary,
    }


def _detail(result: HelpDetailResult) -> JsonObject:
    value = _detail_reference(
        HelpDetailReferenceResult(
            id=result.id,
            operation=result.operation,
            kind=result.kind,
            title=result.title,
            use_when=result.use_when,
            discovery=result.discovery,
            discovery_summary=result.discovery_summary,
        )
    )
    if isinstance(result, HelpComparisonResult):
        value.update(
            {
                "explanation": result.explanation,
                "options": [
                    {"label": option.label, "guidance": option.guidance}
                    for option in result.options
                ],
            }
        )
        return value
    if isinstance(result, HelpTextDetailResult):
        value["body"] = result.body
        return value
    raise TypeError("Unsupported public Help detail result.")


def _operation(result: OperationHelpResult) -> JsonObject:
    return {
        "name": result.name,
        "summary": result.summary,
        "flow": result.flow,
        "execution": result.execution,
        "effect": result.effect,
        "range": result.range,
        "maturity": result.maturity,
        "best_for": result.best_for,
        "use_when": result.use_when,
        "details": [_detail_reference(detail) for detail in result.details],
    }


class HelpAgentAdapter:
    """Expose the public Help facade without granting execution authority."""

    def __init__(self, client: MemCommitClient) -> None:
        if not isinstance(client, MemCommitClient):
            raise TypeError("HelpAgentAdapter requires a MemCommitClient.")
        self._client = client

    def invoke(self, payload: object) -> JsonObject:
        kind: HelpAgentKind | None = None
        try:
            kind, operation_name, detail_id = _parse_request(payload)
        except AgentRequestError as error:
            return error_response(
                version=HELP_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="invalid_request",
                message=str(error),
                retryable=False,
            )
        try:
            if kind == "list":
                result = self._client.list_operations()
                return {
                    "version": HELP_AGENT_CONTRACT_VERSION,
                    "ok": True,
                    "kind": kind,
                    "result": {
                        "operations": [
                            _operation(operation) for operation in result.operations
                        ],
                        "count": len(result.operations),
                        "effect": "NONE",
                    },
                }
            if kind == "list-details":
                result = self._client.list_operation_details(operation_name or "")
                return {
                    "version": HELP_AGENT_CONTRACT_VERSION,
                    "ok": True,
                    "kind": kind,
                    "result": {
                        "operation": result.operation,
                        "details": [
                            _detail_reference(detail) for detail in result.details
                        ],
                        "count": len(result.details),
                        "effect": "NONE",
                    },
                }
            if kind == "describe-detail":
                result = self._client.describe_operation_detail(
                    operation_name or "",
                    detail_id or "",
                )
                return {
                    "version": HELP_AGENT_CONTRACT_VERSION,
                    "ok": True,
                    "kind": kind,
                    "result": {"detail": _detail(result), "effect": "NONE"},
                }
            operation = self._client.describe_operation(operation_name or "")
            return {
                "version": HELP_AGENT_CONTRACT_VERSION,
                "ok": True,
                "kind": kind,
                "result": {
                    "operation": _operation(operation),
                    "effect": "NONE",
                },
            }
        except HelpInputError as error:
            return error_response(
                version=HELP_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="invalid_request",
                message=str(error),
                retryable=False,
            )
        except Exception:
            return error_response(
                version=HELP_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="internal_error",
                message="The Help tool failed internally.",
                retryable=False,
            )


def help_agent_tool_schema() -> JsonObject:
    operation_names = [operation.name for operation in list_operation_help()]
    detail_ids = sorted(
        {
            detail.id
            for operation in list_operation_help()
            for detail in list_operation_details(operation.name)
        }
    )
    return {
        "name": HELP_AGENT_TOOL_NAME,
        "description": (
            "List public MemCommit operations or describe one stable meaning, "
            "flow, execution kind, effect, range, use-when guidance, maturity, "
            "and individually addressable typed details. List detail IDs or "
            "request one full comparison, limitation, access boundary, or "
            "semantic boundary. This "
            "tool executes no operation and changes nothing."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["version", "kind"],
            "properties": {
                "version": {
                    "type": "integer",
                    "const": HELP_AGENT_CONTRACT_VERSION,
                },
                "kind": {
                    "type": "string",
                    "enum": [
                        "list",
                        "describe",
                        "list-details",
                        "describe-detail",
                    ],
                },
                "operation": {
                    "type": "string",
                    "enum": operation_names,
                    "description": "Required for every kind except list.",
                },
                "detail": {
                    "type": "string",
                    "enum": detail_ids,
                    "description": "Required only when kind is describe-detail.",
                },
            },
            "allOf": [
                {
                    "if": {"properties": {"kind": {"const": "list"}}},
                    "then": {"not": {"required": ["operation"]}},
                    "else": {"required": ["operation"]},
                },
                {
                    "if": {"properties": {"kind": {"const": "describe-detail"}}},
                    "then": {"required": ["detail"]},
                    "else": {"not": {"required": ["detail"]}},
                },
            ],
        },
    }


__all__ = [
    "HELP_AGENT_CONTRACT_VERSION",
    "HELP_AGENT_TOOL_NAME",
    "HelpAgentAdapter",
    "HelpAgentKind",
    "help_agent_tool_schema",
]
