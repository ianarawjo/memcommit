"""Versioned JSON-safe agent adapter for semantic Dedun."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from memcommit.adapters.python_api import (
    DedunApplyResult,
    DedunPlanResult,
    MemCommitClient,
    SemanticAuthorityError,
    SemanticConflictError,
    SemanticContextError,
    SemanticError,
    SemanticExecutionError,
    SemanticInputError,
    SemanticStorageError,
)
from memcommit.adapters.interfaces.agent.contract import (
    AgentRequestError,
    JsonObject,
    error_response,
    exact_fields,
    object_value,
    text_value,
)
from memcommit.adapters.interfaces.agent.quality_find import (
    redundancy_evidence_agent_schema,
)
from memcommit.application.reviewing.quality.handoff import (
    QualityFindingHandoff,
    QualityFindingHandoffError,
)
from memcommit.semantic.redundancy_evidence import (
    redundancy_evidence_from_dict,
)


DEDUP_AGENT_CONTRACT_VERSION = 1
DEDUP_AGENT_TOOL_NAME = "memcommit_dedun"
DedupAgentKind = Literal["analyze", "apply"]


def _handoffs(value: object) -> tuple[QualityFindingHandoff, ...]:
    if not isinstance(value, list) or not value:
        raise AgentRequestError("evidence must be a nonempty array.")
    try:
        handoffs = tuple(redundancy_evidence_from_dict(item) for item in value)
    except (QualityFindingHandoffError, TypeError, ValueError) as error:
        raise AgentRequestError(str(error)) from error
    return handoffs


def _survivors(value: object) -> dict[str, str]:
    if not isinstance(value, list) or not value:
        raise AgentRequestError("survivors must be a nonempty array.")
    result: dict[str, str] = {}
    for index, item in enumerate(value):
        selection = object_value(item, label=f"survivors[{index}]")
        exact_fields(
            selection,
            required={"component_uid", "survivor_uid"},
            label=f"survivors[{index}]",
        )
        component_uid = text_value(
            selection["component_uid"],
            field=f"survivors[{index}].component_uid",
        )
        survivor_uid = text_value(
            selection["survivor_uid"],
            field=f"survivors[{index}].survivor_uid",
        )
        if component_uid in result:
            raise AgentRequestError("survivors must not repeat a component_uid.")
        result[component_uid] = survivor_uid
    return result


def _parse_request(
    payload: object,
) -> tuple[
    DedupAgentKind, tuple[QualityFindingHandoff, ...], dict[str, str] | None, str | None
]:
    value = object_value(payload, label="Dedun request")
    version = value.get("version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != DEDUP_AGENT_CONTRACT_VERSION
    ):
        raise AgentRequestError(
            f"version must be exactly {DEDUP_AGENT_CONTRACT_VERSION}."
        )
    kind = value.get("kind")
    if kind not in {"analyze", "apply"}:
        raise AgentRequestError("kind must be analyze or apply.")
    required = {"version", "kind", "evidence"}
    if kind == "apply":
        required |= {"survivors", "expected_revision"}
    exact_fields(value, required=required, label=f"Dedun {kind} request")
    handoffs = _handoffs(value["evidence"])
    if kind == "analyze":
        return "analyze", handoffs, None, None
    return (
        "apply",
        handoffs,
        _survivors(value["survivors"]),
        text_value(value["expected_revision"], field="expected_revision"),
    )


def _plan_result(result: DedunPlanResult) -> JsonObject:
    return {
        "context_name": result.context_name,
        "context_uid": result.context_uid,
        "revision": result.revision,
        "components": [
            {
                "uid": component.uid,
                "recommended_survivor_uid": component.recommended_survivor_uid,
                "members": [
                    {
                        "uid": member.uid,
                        "content": member.content,
                        "ordinal": member.ordinal,
                        "recommended": member.recommended,
                    }
                    for member in component.members
                ],
                "evidence": [
                    {
                        "finding_uid": evidence.finding_uid,
                        "relation": evidence.relation,
                        "left_uid": evidence.left_uid,
                        "right_uid": evidence.right_uid,
                        "reason": evidence.reason,
                    }
                    for evidence in component.evidence
                ],
            }
            for component in result.components
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
    }


def _apply_result(result: DedunApplyResult) -> JsonObject:
    return {
        "context_name": result.context_name,
        "context_uid": result.context_uid,
        "revision": result.revision,
        "checkpoint_uid": result.checkpoint_uid,
        "survivor_uids": list(result.survivor_uids),
        "absorbed_uids": list(result.absorbed_uids),
        "effect": "CHECKPOINT",
    }


_PUBLIC_ERRORS: tuple[tuple[type[SemanticError], str, str], ...] = (
    (SemanticInputError, "invalid_request", "The Dedun request is invalid."),
    (SemanticContextError, "context_unavailable", "The Dedun Context is unavailable."),
    (SemanticAuthorityError, "authority_denied", "Dedun authority was denied."),
    (SemanticConflictError, "concurrent_update", "The Dedun Source changed."),
    (SemanticStorageError, "storage_failure", "Dedun storage failed safely."),
    (
        SemanticExecutionError,
        "execution_failed",
        "Dedun failed before publishing a complete outcome.",
    ),
)


class DedupAgentAdapter:
    """Expose semantic redundancy planning and stateless exact replay."""

    def __init__(self, client: MemCommitClient) -> None:
        if not isinstance(client, MemCommitClient):
            raise TypeError("Dedun adapter requires a MemCommitClient.")
        self._client = client

    def invoke(self, payload: object) -> JsonObject:
        kind: DedupAgentKind | None = None
        if isinstance(payload, Mapping) and payload.get("kind") in {"analyze", "apply"}:
            kind = payload["kind"]  # type: ignore[assignment]
        try:
            kind, handoffs, survivors, expected_revision = _parse_request(payload)
        except AgentRequestError as error:
            return error_response(
                version=DEDUP_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="invalid_request",
                message=str(error),
                retryable=False,
            )
        try:
            plan = self._client.plan_dedun(
                handoffs,
                expected_revision=expected_revision,
            )
            result = (
                _plan_result(plan)
                if kind == "analyze"
                else _apply_result(
                    self._client.apply_dedun(
                        plan,
                        survivors=survivors or {},
                    )
                )
            )
        except SemanticError as error:
            for error_type, code, message in _PUBLIC_ERRORS:
                if isinstance(error, error_type):
                    return error_response(
                        version=DEDUP_AGENT_CONTRACT_VERSION,
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
                        retryable=False,
                    )
            return error_response(
                version=DEDUP_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="dedun_failed",
                message="Dedun failed without a more specific public category.",
                retryable=False,
            )
        except Exception:
            return error_response(
                version=DEDUP_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="internal_error",
                message="The Dedun tool failed internally.",
                retryable=False,
            )
        return {
            "version": DEDUP_AGENT_CONTRACT_VERSION,
            "ok": True,
            "kind": kind,
            "result": result,
        }


def dedup_agent_tool_schema() -> JsonObject:
    text = {"type": "string", "minLength": 1, "pattern": r".*\S.*"}
    return {
        "name": DEDUP_AGENT_TOOL_NAME,
        "description": (
            "Plan groups from confirmed exact or semantic redundancy evidence, "
            "or revalidate and atomically apply one exact existing-survivor choice "
            "per group. Dedun never rewrites Memory content."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["version", "kind", "evidence"],
            "properties": {
                "version": {"type": "integer", "const": DEDUP_AGENT_CONTRACT_VERSION},
                "kind": {"type": "string", "enum": ["analyze", "apply"]},
                "evidence": {
                    "type": "array",
                    "minItems": 1,
                    "items": redundancy_evidence_agent_schema(),
                },
                "survivors": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["component_uid", "survivor_uid"],
                        "properties": {
                            "component_uid": text,
                            "survivor_uid": text,
                        },
                    },
                },
                "expected_revision": text,
            },
        },
    }


__all__ = [
    "DEDUP_AGENT_CONTRACT_VERSION",
    "DEDUP_AGENT_TOOL_NAME",
    "DedupAgentAdapter",
    "DedupAgentKind",
    "dedup_agent_tool_schema",
]
