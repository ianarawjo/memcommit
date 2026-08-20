"""Versioned read-only agent adapter for Elaborate."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from memcommit.api import (
    ElaborateProposal,
    MemCommitClient,
    SemanticConflictError,
    SemanticContextError,
    SemanticError,
    SemanticExecutionError,
    SemanticInputError,
    SemanticProviderFailure,
    SemanticStorageError,
)
from memcommit.elaborate_config import DEFAULT_ELABORATE_SEMANTIC_CONFIG
from memcommit.interfaces.agent.contract import (
    AgentRequestError,
    JsonObject,
    error_response,
    exact_fields,
    object_value,
    text_value,
)


ELABORATE_AGENT_CONTRACT_VERSION = 2
ELABORATE_AGENT_TOOL_NAME = "memcommit_elaborate"
ElaborateAgentKind = Literal[
    "goal_to_rules",
    "rules_to_cases",
    "ground_goal_to_rules",
    "ground_rules_to_cases",
]


def _parse_request(payload: object) -> tuple[ElaborateAgentKind, dict[str, object]]:
    value = object_value(payload, label="Elaborate request")
    if value.get("version") != ELABORATE_AGENT_CONTRACT_VERSION or isinstance(
        value.get("version"), bool
    ):
        raise AgentRequestError(
            f"version must be exactly {ELABORATE_AGENT_CONTRACT_VERSION}."
        )
    kind = value.get("kind")
    if kind == "goal_to_rules":
        exact_fields(
            value,
            required={"version", "kind", "goal"},
            optional=frozenset({"number"}),
            label="Goal Elaborate request",
        )
        return kind, {
            "goal": text_value(value["goal"], field="goal"),
            "number": _number_value(
                value.get("number"),
                maximum=DEFAULT_ELABORATE_SEMANTIC_CONFIG.max_rule_proposals,
            ),
        }
    if kind == "rules_to_cases":
        exact_fields(
            value,
            required={"version", "kind", "rules"},
            optional=frozenset({"number"}),
            label="Rules Elaborate request",
        )
        raw = value["rules"]
        if not isinstance(raw, list) or not raw:
            raise AgentRequestError("rules must be a nonempty list of Rule texts.")
        return kind, {
            "rules": tuple(text_value(item, field="rules item") for item in raw),
            "number": _number_value(
                value.get("number"),
                maximum=DEFAULT_ELABORATE_SEMANTIC_CONFIG.max_case_proposals,
            ),
        }
    if kind in {"ground_goal_to_rules", "ground_rules_to_cases"}:
        exact_fields(
            value,
            required={"version", "kind", "ground_name"},
            optional=frozenset({"number"}),
            label="Ground Elaborate request",
        )
        return kind, {
            "ground_name": text_value(value["ground_name"], field="ground_name"),
            "direction": "GOAL_TO_RULES" if kind == "ground_goal_to_rules" else "RULES_TO_CASES",
            "number": _number_value(
                value.get("number"),
                maximum=(
                    DEFAULT_ELABORATE_SEMANTIC_CONFIG.max_rule_proposals
                    if kind == "ground_goal_to_rules"
                    else DEFAULT_ELABORATE_SEMANTIC_CONFIG.max_case_proposals
                ),
            ),
        }
    raise AgentRequestError(
        "kind must be one of: goal_to_rules, rules_to_cases, "
        "ground_goal_to_rules, ground_rules_to_cases."
    )


def _number_value(value: object, *, maximum: int) -> int | None:
    if value is None:
        return None
    if type(value) is not int or not 1 <= value <= maximum:
        raise AgentRequestError(f"number must be an integer from 1 to {maximum}.")
    return value


def _serialize(result: ElaborateProposal) -> JsonObject:
    return {
        "analysis_uid": result.analysis_uid,
        "mode": result.mode,
        "inputs": list(result.inputs),
        "overview": result.overview,
        "rules": [
            {"uid": item.uid, "content": item.content, "rationale": item.rationale}
            for item in result.rules
        ],
        "cases": [
            {
                "uid": item.uid,
                "proposition": item.proposition,
                "expected": item.expected,
                "rationale": item.rationale,
                "case_role": item.case_role,
                "rule_checks": [
                    {
                        "source_rule_index": check.source_rule_index,
                        "evidence": check.evidence,
                    }
                    for check in item.rule_checks
                ],
            }
            for item in result.cases
        ],
        "origin": result.origin,
        "verification": result.verification,
        "effect": "NONE",
    }


class ElaborateAgentAdapter:
    def __init__(self, client: MemCommitClient) -> None:
        if not isinstance(client, MemCommitClient):
            raise TypeError("ElaborateAgentAdapter requires a MemCommitClient.")
        self._client = client

    def invoke(self, payload: object) -> JsonObject:
        kind: ElaborateAgentKind | None = None
        valid = {
            "goal_to_rules",
            "rules_to_cases",
            "ground_goal_to_rules",
            "ground_rules_to_cases",
        }
        if isinstance(payload, Mapping) and payload.get("kind") in valid:
            kind = payload["kind"]  # type: ignore[assignment]
        try:
            kind, arguments = _parse_request(payload)
        except AgentRequestError as error:
            return error_response(
                version=ELABORATE_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="invalid_request",
                message=str(error),
                retryable=False,
            )
        try:
            result = (
                self._client.elaborate(**arguments)  # type: ignore[arg-type]
                if kind in {"goal_to_rules", "rules_to_cases"}
                else self._client.elaborate_ground(**arguments)  # type: ignore[arg-type]
            )
        except SemanticError as error:
            if isinstance(error, SemanticInputError):
                code, message, retryable = "invalid_request", str(error), False
            elif isinstance(error, SemanticContextError):
                code, message, retryable = "context_unavailable", str(error), False
            elif isinstance(error, SemanticConflictError):
                code, message, retryable = (
                    "stale_state",
                    "The Elaborate Ground changed.",
                    False,
                )
            elif isinstance(error, SemanticProviderFailure):
                code, message, retryable = "provider_failure", "The Elaborate provider failed.", True
            elif isinstance(error, SemanticStorageError):
                code, message, retryable = "storage_failure", "Elaborate could not access local state.", False
            elif isinstance(error, SemanticExecutionError):
                code, message, retryable = "execution_failed", "Elaborate failed before publishing proposals.", False
            else:
                code, message, retryable = "elaborate_failed", "Elaborate failed.", False
            return error_response(
                version=ELABORATE_AGENT_CONTRACT_VERSION,
                kind=kind,
                code=code,
                message=message,
                retryable=retryable,
            )
        except Exception:
            return error_response(
                version=ELABORATE_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="internal_error",
                message="The Elaborate tool failed internally.",
                retryable=False,
            )
        return {
            "version": ELABORATE_AGENT_CONTRACT_VERSION,
            "ok": True,
            "kind": kind,
            "result": _serialize(result),
        }


def elaborate_agent_tool_schema() -> JsonObject:
    text = {"type": "string", "minLength": 1, "pattern": r".*\S.*"}
    version = {"type": "integer", "const": ELABORATE_AGENT_CONTRACT_VERSION}
    branches = []
    for kind, field in (("goal_to_rules", "goal"), ("rules_to_cases", "rules")):
        value_schema: JsonObject = text if field == "goal" else {
            "type": "array", "minItems": 1, "uniqueItems": True, "items": text
        }
        branches.append(
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["version", "kind", field],
                "properties": {
                    "version": version,
                    "kind": {"type": "string", "const": kind},
                    field: value_schema,
                    "number": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": (
                            DEFAULT_ELABORATE_SEMANTIC_CONFIG.max_rule_proposals
                            if kind == "goal_to_rules"
                            else DEFAULT_ELABORATE_SEMANTIC_CONFIG.max_case_proposals
                        ),
                    },
                },
            }
        )
    for kind in ("ground_goal_to_rules", "ground_rules_to_cases"):
        branches.append(
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["version", "kind", "ground_name"],
                "properties": {
                    "version": version,
                    "kind": {"type": "string", "const": kind},
                    "ground_name": text,
                    "number": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": (
                            DEFAULT_ELABORATE_SEMANTIC_CONFIG.max_rule_proposals
                            if kind == "ground_goal_to_rules"
                            else DEFAULT_ELABORATE_SEMANTIC_CONFIG.max_case_proposals
                        ),
                    },
                },
            }
        )
    return {
        "name": ELABORATE_AGENT_TOOL_NAME,
        "description": (
            "Propose unverified Rules from a Goal or Cases from Rules, using "
            "inline input or one exact Ground; nothing is saved or accepted."
        ),
        "parameters": {"type": "object", "oneOf": branches},
    }


__all__ = [
    "ELABORATE_AGENT_CONTRACT_VERSION",
    "ELABORATE_AGENT_TOOL_NAME",
    "ElaborateAgentAdapter",
    "elaborate_agent_tool_schema",
]
