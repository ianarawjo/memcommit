"""Versioned agent contract for Ground Fit and explicit Resolve review."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from memcommit.api import (
    DistillProposal,
    ElaborateProposal,
    GroundFitReceiptResult,
    MemCommitClient,
    SemanticConflictError,
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
from memcommit.interfaces.agent.ground_artifacts import GroundArtifactRegistry


GROUND_RESOLUTION_AGENT_CONTRACT_VERSION = 1
GROUND_RESOLUTION_AGENT_TOOL_NAME = "memcommit_ground_resolve"
GroundResolutionAgentKind = Literal[
    "fit_ground",
    "plan_candidate",
    "plan_fit",
    "apply",
]
_FIT_ACTIONS = {
    "REVISE_GOAL",
    "REFINE_RULE",
    "REFINE_EXAMPLE",
    "SET_EXAMPLE_USE",
    "DEFER",
}


def _parse_request(payload: object) -> tuple[GroundResolutionAgentKind, dict]:
    value = object_value(payload, label="Ground Resolve request")
    version = value.get("version")
    if version != GROUND_RESOLUTION_AGENT_CONTRACT_VERSION or isinstance(
        version,
        bool,
    ):
        raise AgentRequestError(
            f"version must be exactly {GROUND_RESOLUTION_AGENT_CONTRACT_VERSION}."
        )
    kind = value.get("kind")
    if kind == "fit_ground":
        exact_fields(
            value,
            required={"version", "kind", "ground_name"},
            optional=frozenset({"receipt_uid"}),
            label="Ground Fit request",
        )
        return kind, {
            "ground_name": text_value(value["ground_name"], field="ground_name"),
            "receipt_uid": text_value(
                value.get("receipt_uid"),
                field="receipt_uid",
                optional=True,
            ),
        }
    if kind == "plan_candidate":
        exact_fields(
            value,
            required={"version", "kind", "artifact_uid", "candidate_uid"},
            label="Ground candidate Resolve request",
        )
        return kind, {
            "artifact_uid": text_value(
                value["artifact_uid"],
                field="artifact_uid",
            ),
            "candidate_uid": text_value(
                value["candidate_uid"],
                field="candidate_uid",
            ),
        }
    if kind == "plan_fit":
        exact_fields(
            value,
            required={"version", "kind", "artifact_uid", "example_uid", "action"},
            optional=frozenset({"content", "rationale", "rule_uid", "use"}),
            label="Ground Fit Resolve request",
        )
        action = value["action"]
        if action not in _FIT_ACTIONS:
            raise AgentRequestError(
                "action must be REVISE_GOAL, REFINE_RULE, REFINE_EXAMPLE, "
                "SET_EXAMPLE_USE, or DEFER."
            )
        return kind, {
            "artifact_uid": text_value(
                value["artifact_uid"],
                field="artifact_uid",
            ),
            "example_uid": text_value(value["example_uid"], field="example_uid"),
            "action": action,
            "content": text_value(
                value.get("content"),
                field="content",
                optional=True,
            )
            or "",
            "rationale": text_value(
                value.get("rationale"),
                field="rationale",
                optional=True,
            )
            or "",
            "rule_uid": text_value(
                value.get("rule_uid"),
                field="rule_uid",
                optional=True,
            )
            or "",
            "use": text_value(
                value.get("use"),
                field="use",
                optional=True,
            )
            or "",
        }
    if kind == "apply":
        exact_fields(
            value,
            required={"version", "kind", "plan_digest"},
            label="Ground Resolve Apply request",
        )
        return kind, {
            "plan_digest": text_value(
                value["plan_digest"],
                field="plan_digest",
            )
        }
    raise AgentRequestError(
        "kind must be one of: fit_ground, plan_candidate, plan_fit, apply."
    )


def _fit_result(result: GroundFitReceiptResult) -> JsonObject:
    return {
        "artifact_uid": result.receipt_uid,
        "artifact_kind": "FIT",
        "artifact_digest": result.receipt_digest,
        "ground_name": result.ground_name,
        "ground_revision": result.ground_revision,
        "ground_digest": result.ground_digest,
        "current": result.current,
        "overview": result.overview,
        "judgments": [
            {
                "example_uid": item.example_uid,
                "example_alias": item.example_alias,
                "proposition": item.proposition,
                "status": item.status,
                "reason": item.reason,
                "rule_uids": list(item.rule_uids),
            }
            for item in result.judgments
        ],
        "effect": "NONE",
    }


def _plan_result(result) -> JsonObject:
    action = result.action
    return {
        "plan_digest": result.plan_digest,
        "artifact_kind": result.artifact_kind,
        "artifact_uid": result.artifact_uid,
        "artifact_digest": result.artifact_digest,
        "source_verification": result.source_verification,
        "candidate_verification": result.candidate_verification,
        "ground_uid": result.ground_uid,
        "ground_name": result.ground_name,
        "ground_revision": result.ground_revision,
        "ground_digest": result.ground_digest,
        "explanation": result.explanation,
        "action": {
            "kind": action.kind,
            "content": action.content,
            "rationale": action.rationale,
            "selector": action.selector,
            "source_item_uid": action.source_item_uid,
            "case_role": action.case_role,
            "use": action.use,
            "rule_provenance": action.rule_provenance,
        },
        "effect": "NONE",
        "apply_request": {
            "version": GROUND_RESOLUTION_AGENT_CONTRACT_VERSION,
            "kind": "apply",
            "plan_digest": result.plan_digest,
        },
    }


def _semantic_error(
    kind: GroundResolutionAgentKind | None,
    error: SemanticError,
) -> JsonObject:
    if isinstance(error, SemanticInputError):
        code, message, retryable = "invalid_request", str(error), False
    elif isinstance(error, SemanticContextError):
        code, message, retryable = "context_unavailable", str(error), False
    elif isinstance(error, SemanticConflictError):
        code, message, retryable = "stale_state", str(error), False
    elif isinstance(error, SemanticProviderFailure):
        code, message, retryable = "provider_failure", "The provider failed.", True
    elif isinstance(error, SemanticStorageError):
        code, message, retryable = (
            "storage_failure",
            "Ground Resolve could not access local state.",
            False,
        )
    elif isinstance(error, SemanticExecutionError):
        code, message, retryable = (
            "execution_failed",
            "Ground Resolve failed before a complete outcome.",
            False,
        )
    else:
        code, message, retryable = "resolve_failed", "Ground Resolve failed.", False
    return error_response(
        version=GROUND_RESOLUTION_AGENT_CONTRACT_VERSION,
        kind=kind,
        code=code,
        message=message,
        retryable=retryable,
    )


class GroundResolutionAgentAdapter:
    """Keep read-only analysis, review, and exact Apply as separate calls."""

    def __init__(
        self,
        client: MemCommitClient,
        artifacts: GroundArtifactRegistry,
    ) -> None:
        if not isinstance(client, MemCommitClient):
            raise TypeError("GroundResolutionAgentAdapter requires a MemCommitClient.")
        if not isinstance(artifacts, GroundArtifactRegistry):
            raise TypeError(
                "GroundResolutionAgentAdapter requires a GroundArtifactRegistry."
            )
        self._client = client
        self._artifacts = artifacts

    def invoke(self, payload: object) -> JsonObject:
        kind: GroundResolutionAgentKind | None = None
        if isinstance(payload, Mapping) and payload.get("kind") in {
            "fit_ground",
            "plan_candidate",
            "plan_fit",
            "apply",
        }:
            kind = payload["kind"]  # type: ignore[assignment]
        try:
            kind, arguments = _parse_request(payload)
        except AgentRequestError as error:
            return error_response(
                version=GROUND_RESOLUTION_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="invalid_request",
                message=str(error),
                retryable=False,
            )
        try:
            if kind == "fit_ground":
                fit = self._client.fit_ground(**arguments)
                self._artifacts.retain_artifact(fit)
                return {
                    "version": GROUND_RESOLUTION_AGENT_CONTRACT_VERSION,
                    "ok": True,
                    "kind": kind,
                    "result": _fit_result(fit),
                }
            if kind in {"plan_candidate", "plan_fit"}:
                artifact_uid = arguments.pop("artifact_uid")
                source = self._artifacts.artifact(artifact_uid)
                if source is None:
                    return error_response(
                        version=GROUND_RESOLUTION_AGENT_CONTRACT_VERSION,
                        kind=kind,
                        code="artifact_expired",
                        message="The process-local artifact is unavailable; rerun its analysis.",
                        retryable=False,
                    )
                if kind == "plan_candidate" and not isinstance(
                    source,
                    (DistillProposal, ElaborateProposal),
                ):
                    raise SemanticInputError(
                        "plan_candidate requires a Ground Distill or Elaborate artifact."
                    )
                if kind == "plan_fit" and not isinstance(
                    source,
                    GroundFitReceiptResult,
                ):
                    raise SemanticInputError(
                        "plan_fit requires a Ground Fit artifact."
                    )
                plan = self._client.plan_ground_resolution(source, **arguments)
                self._artifacts.retain_plan(plan)
                return {
                    "version": GROUND_RESOLUTION_AGENT_CONTRACT_VERSION,
                    "ok": True,
                    "kind": kind,
                    "result": _plan_result(plan),
                }
            plan = self._artifacts.plan(arguments["plan_digest"])
            if plan is None:
                return error_response(
                    version=GROUND_RESOLUTION_AGENT_CONTRACT_VERSION,
                    kind=kind,
                    code="plan_expired",
                    message="The process-local Resolve plan is unavailable; plan it again.",
                    retryable=False,
                )
            receipt = self._client.apply_ground_resolution(plan)
            return {
                "version": GROUND_RESOLUTION_AGENT_CONTRACT_VERSION,
                "ok": True,
                "kind": kind,
                "result": {
                    "plan_digest": receipt.plan_digest,
                    "artifact_uid": receipt.artifact_uid,
                    "action_kind": receipt.action_kind,
                    "previous_revision": receipt.previous_revision,
                    "resulting_revision": receipt.resulting_revision,
                    "resulting_ground_digest": receipt.resulting_ground_digest,
                    "mutated": receipt.mutated,
                    "effect": "GROUND_REVISION" if receipt.mutated else "NONE",
                },
            }
        except SemanticError as error:
            return _semantic_error(kind, error)
        except Exception:
            return error_response(
                version=GROUND_RESOLUTION_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="internal_error",
                message="The Ground Resolve tool failed internally.",
                retryable=False,
            )


def ground_resolution_agent_tool_schema() -> JsonObject:
    text = {"type": "string", "minLength": 1, "pattern": r".*\S.*"}
    version = {
        "type": "integer",
        "const": GROUND_RESOLUTION_AGENT_CONTRACT_VERSION,
    }
    base = {"version": version}
    fit_action = {
        "type": "string",
        "enum": sorted(_FIT_ACTIONS),
    }
    return {
        "name": GROUND_RESOLUTION_AGENT_TOOL_NAME,
        "description": (
            "Run or reopen Ground Fit, plan exactly one action from a retained "
            "Ground Fit/Distill/Elaborate artifact, then apply only a separately "
            "reviewed plan digest through Ground CAS."
        ),
        "parameters": {
            "type": "object",
            "oneOf": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["version", "kind", "ground_name"],
                    "properties": {
                        **base,
                        "kind": {"type": "string", "const": "fit_ground"},
                        "ground_name": text,
                        "receipt_uid": text,
                    },
                },
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "version",
                        "kind",
                        "artifact_uid",
                        "candidate_uid",
                    ],
                    "properties": {
                        **base,
                        "kind": {"type": "string", "const": "plan_candidate"},
                        "artifact_uid": text,
                        "candidate_uid": text,
                    },
                },
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "version",
                        "kind",
                        "artifact_uid",
                        "example_uid",
                        "action",
                    ],
                    "properties": {
                        **base,
                        "kind": {"type": "string", "const": "plan_fit"},
                        "artifact_uid": text,
                        "example_uid": text,
                        "action": fit_action,
                        "content": {"type": "string"},
                        "rationale": {"type": "string"},
                        "rule_uid": {"type": "string"},
                        "use": {
                            "type": "string",
                            "enum": ["INCLUDE", "EXCLUDE"],
                        },
                    },
                },
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["version", "kind", "plan_digest"],
                    "properties": {
                        **base,
                        "kind": {"type": "string", "const": "apply"},
                        "plan_digest": text,
                    },
                },
            ],
        },
    }


__all__ = [
    "GROUND_RESOLUTION_AGENT_CONTRACT_VERSION",
    "GROUND_RESOLUTION_AGENT_TOOL_NAME",
    "GroundResolutionAgentAdapter",
    "ground_resolution_agent_tool_schema",
]
