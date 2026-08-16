"""Versioned read-only agent adapter for operation discovery."""

from __future__ import annotations

from typing import Literal

from memcommit.api import (
    HelpInputError,
    MemCommitClient,
    OperationHelpResult,
)
from memcommit.help_application import list_operation_help
from memcommit.interfaces.agent.contract import (
    AgentRequestError,
    JsonObject,
    error_response,
    exact_fields,
    object_value,
    text_value,
)


HELP_AGENT_CONTRACT_VERSION = 1
HELP_AGENT_TOOL_NAME = "memcommit_help"
HelpAgentKind = Literal["list", "describe"]


def _parse_request(payload: object) -> tuple[HelpAgentKind, str | None]:
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
        return "list", None
    if kind == "describe":
        exact_fields(
            value,
            required={"version", "kind", "operation"},
            label="Help describe request",
        )
        return "describe", text_value(value["operation"], field="operation")
    raise AgentRequestError("kind must be one of: list, describe.")


def _operation(result: OperationHelpResult) -> JsonObject:
    return {
        "name": result.name,
        "summary": result.summary,
        "flow": result.flow,
        "execution": result.execution,
        "effect": result.effect,
        "range": result.range,
        "best_for": result.best_for,
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
            kind, operation_name = _parse_request(payload)
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
    return {
        "name": HELP_AGENT_TOOL_NAME,
        "description": (
            "List public MemCommit operations or describe one stable meaning, "
            "flow, execution kind, effect, range, and best-use situation. This "
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
                "kind": {"type": "string", "enum": ["list", "describe"]},
                "operation": {
                    "type": "string",
                    "enum": operation_names,
                    "description": "Required only when kind is describe.",
                },
            },
            "allOf": [
                {
                    "if": {"properties": {"kind": {"const": "describe"}}},
                    "then": {"required": ["operation"]},
                    "else": {"not": {"required": ["operation"]}},
                }
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
