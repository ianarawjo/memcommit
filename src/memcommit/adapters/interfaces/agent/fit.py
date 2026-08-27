"""Versioned read-only agent adapter for role-neutral Fit."""

from __future__ import annotations

from memcommit.adapters.python_api import (
    FitPropositionInput,
    MemCommitClient,
    SemanticError,
    SemanticExecutionError,
    SemanticInputError,
    SemanticProviderFailure,
)
from memcommit.adapters.interfaces.agent.contract import (
    AgentRequestError,
    JsonObject,
    error_response,
    exact_fields,
    object_value,
    text_value,
)


FIT_AGENT_CONTRACT_VERSION = 1
FIT_AGENT_TOOL_NAME = "memcommit_fit"
_ROLES = {"PROPOSITION", "MEMORY", "RULE", "GOAL", "EXAMPLE"}


def _proposition(value: object, *, field: str) -> FitPropositionInput:
    data = object_value(value, label=field)
    exact_fields(
        data,
        required={"content"},
        optional=frozenset({"role", "alias"}),
        label=field,
    )
    role = data.get("role", "PROPOSITION")
    if role not in _ROLES:
        raise AgentRequestError(
            f"{field}.role must be PROPOSITION, MEMORY, RULE, GOAL, or EXAMPLE."
        )
    return FitPropositionInput(
        content=text_value(data["content"], field=f"{field}.content"),
        role=role,  # type: ignore[arg-type]
        alias=text_value(data.get("alias"), field=f"{field}.alias", optional=True),
    )


def _propositions(
    value: object,
    *,
    field: str,
    minimum: int,
) -> tuple[FitPropositionInput, ...]:
    if not isinstance(value, list) or len(value) < minimum:
        qualifier = "at least two" if minimum == 2 else "zero or more"
        raise AgentRequestError(f"{field} must contain {qualifier} propositions.")
    return tuple(
        _proposition(item, field=f"{field}[{index}]")
        for index, item in enumerate(value)
    )


def _parse_request(
    payload: object,
) -> tuple[tuple[FitPropositionInput, ...], tuple[FitPropositionInput, ...]]:
    value = object_value(payload, label="Fit request")
    exact_fields(
        value,
        required={"version", "propositions"},
        optional=frozenset({"background"}),
        label="Fit request",
    )
    if value.get("version") != FIT_AGENT_CONTRACT_VERSION or isinstance(
        value.get("version"), bool
    ):
        raise AgentRequestError(
            f"version must be exactly {FIT_AGENT_CONTRACT_VERSION}."
        )
    propositions = _propositions(
        value["propositions"],
        field="propositions",
        minimum=2,
    )
    raw_background = value.get("background", [])
    if not isinstance(raw_background, list):
        raise AgentRequestError("background must be an array.")
    background = tuple(
        _proposition(item, field=f"background[{index}]")
        for index, item in enumerate(raw_background)
    )
    return propositions, background


class FitAgentAdapter:
    """Expose one exact set-level compatibility judgment to agent hosts."""

    def __init__(self, client: MemCommitClient) -> None:
        if not isinstance(client, MemCommitClient):
            raise TypeError("FitAgentAdapter requires a MemCommitClient.")
        self._client = client

    def invoke(self, payload: object) -> JsonObject:
        try:
            propositions, background = _parse_request(payload)
        except AgentRequestError as error:
            return error_response(
                version=FIT_AGENT_CONTRACT_VERSION,
                kind="propositions",
                code="invalid_request",
                message=str(error),
                retryable=False,
            )
        try:
            result = self._client.fit(propositions, background=background)
        except SemanticInputError as error:
            return error_response(
                version=FIT_AGENT_CONTRACT_VERSION,
                kind="propositions",
                code="invalid_request",
                message=str(error),
                retryable=False,
            )
        except SemanticProviderFailure:
            return error_response(
                version=FIT_AGENT_CONTRACT_VERSION,
                kind="propositions",
                code="provider_failure",
                message="The Fit provider failed.",
                retryable=True,
            )
        except SemanticExecutionError:
            return error_response(
                version=FIT_AGENT_CONTRACT_VERSION,
                kind="propositions",
                code="execution_failed",
                message="Fit failed before returning a complete judgment.",
                retryable=False,
            )
        except SemanticError:
            return error_response(
                version=FIT_AGENT_CONTRACT_VERSION,
                kind="propositions",
                code="fit_failed",
                message="Fit failed without a more specific public category.",
                retryable=False,
            )
        except Exception:
            return error_response(
                version=FIT_AGENT_CONTRACT_VERSION,
                kind="propositions",
                code="internal_error",
                message="The Fit tool failed internally.",
                retryable=False,
            )
        return {
            "version": FIT_AGENT_CONTRACT_VERSION,
            "ok": True,
            "kind": "propositions",
            "result": {
                "analysis_uid": result.analysis_uid,
                "verdict": result.verdict,
                "reason": result.reason,
                "considered_aliases": list(result.considered_aliases),
                "material_aliases": list(result.material_aliases),
                "consistent_reading": result.consistent_reading,
                "inconsistent_reading": result.inconsistent_reading,
                "effect": "NONE",
            },
        }


def fit_agent_tool_schema() -> JsonObject:
    text = {"type": "string", "minLength": 1, "pattern": r".*\S.*"}
    proposition = {
        "type": "object",
        "additionalProperties": False,
        "required": ["content"],
        "properties": {
            "content": text,
            "role": {
                "type": "string",
                "enum": ["PROPOSITION", "MEMORY", "RULE", "GOAL", "EXAMPLE"],
                "default": "PROPOSITION",
            },
            "alias": {**text, "type": ["string", "null"]},
        },
    }
    return {
        "name": FIT_AGENT_TOOL_NAME,
        "description": (
            "Judge whether one complete set of two or more propositions can "
            "jointly hold under materially ordinary readings; changes nothing."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["version", "propositions"],
            "properties": {
                "version": {
                    "type": "integer",
                    "const": FIT_AGENT_CONTRACT_VERSION,
                },
                "propositions": {
                    "type": "array",
                    "minItems": 2,
                    "items": proposition,
                },
                "background": {
                    "type": "array",
                    "items": proposition,
                    "default": [],
                },
            },
        },
    }


__all__ = [
    "FIT_AGENT_CONTRACT_VERSION",
    "FIT_AGENT_TOOL_NAME",
    "FitAgentAdapter",
    "fit_agent_tool_schema",
]
