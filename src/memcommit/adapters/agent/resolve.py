"""Versioned JSON-safe agent adapter for exact Resolve analysis and Apply."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from memcommit.adapters.python_api import (
    MemCommitClient,
    ResolveAnalysisResult,
    ResolveApplyResult,
    ResolveDecisionInput,
    SemanticAuthorityError,
    SemanticConflictError,
    SemanticContextError,
    SemanticError,
    SemanticExecutionError,
    SemanticInputError,
    SemanticProviderFailure,
    SemanticStorageError,
)
from memcommit.adapters.agent.contract import (
    AgentRequestError,
    JsonObject,
    error_response,
    exact_fields,
    object_value,
    text_value,
)
from memcommit.adapters.agent.quality_find import (
    quality_finding_handoff_agent_schema,
)
from memcommit.application.capabilities.memory_issue_analysis.handoff import (
    QualityFindingHandoff,
    QualityFindingHandoffError,
)


RESOLVE_AGENT_CONTRACT_VERSION = 4
RESOLVE_AGENT_TOOL_NAME = "memcommit_resolve"
RESOLVE_AGENT_ANALYSIS_CACHE_LIMIT = 64
ResolveAgentKind = Literal["analyze", "apply"]


def _boolean(value: object, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise AgentRequestError(f"{field} must be a boolean.")
    return value


def _selectors(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise AgentRequestError("memory_selectors must be an array.")
    selectors = tuple(
        text_value(item, field=f"memory_selectors[{index}]")
        for index, item in enumerate(value)
    )
    if len(set(selectors)) != len(selectors):
        raise AgentRequestError("memory_selectors must not repeat.")
    return selectors


def _decisions(value: object) -> tuple[ResolveDecisionInput, ...]:
    if not isinstance(value, list):
        raise AgentRequestError("decisions must be an array.")
    result: list[ResolveDecisionInput] = []
    for index, item in enumerate(value):
        record = object_value(item, label=f"decisions[{index}]")
        exact_fields(
            record,
            required={"issue_uid", "kind"},
            optional={"intent"},
            label=f"decisions[{index}]",
        )
        kind = record["kind"]
        if kind not in {"CONFIRM", "INTENT", "FORCE"}:
            raise AgentRequestError(
                f"decisions[{index}].kind must be CONFIRM, INTENT, or FORCE."
            )
        result.append(
            ResolveDecisionInput(
                issue_uid=text_value(
                    record["issue_uid"],
                    field=f"decisions[{index}].issue_uid",
                ),
                kind=kind,
                intent=(
                    text_value(
                        record["intent"],
                        field=f"decisions[{index}].intent",
                    )
                    if "intent" in record
                    else ""
                ),
            )
        )
    return tuple(result)


def _parse_request(payload: object) -> tuple[ResolveAgentKind, dict[str, object]]:
    value = object_value(payload, label="Resolve request")
    version = value.get("version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != RESOLVE_AGENT_CONTRACT_VERSION
    ):
        raise AgentRequestError(
            f"version must be exactly {RESOLVE_AGENT_CONTRACT_VERSION}."
        )
    kind = value.get("kind")
    if kind not in {"analyze", "apply"}:
        raise AgentRequestError("kind must be analyze or apply.")
    common = {
        "context_name",
        "memory_selectors",
        "allow_create",
        "allow_delete",
        "guidance",
        "finding_handoff",
    }
    required = {"version", "kind"}
    optional = common
    if kind == "apply":
        required |= {"decisions", "expected_revision"}
    exact_fields(
        value,
        required=required,
        optional=frozenset(optional),
        label=f"Resolve {kind} request",
    )
    arguments: dict[str, object] = {
        "context_name": text_value(
            value.get("context_name"),
            field="context_name",
            optional=True,
        ),
        "memory_selectors": _selectors(value.get("memory_selectors", [])),
        "allow_create": _boolean(
            value.get("allow_create", True),
            field="allow_create",
        ),
        "allow_delete": _boolean(
            value.get("allow_delete", False),
            field="allow_delete",
        ),
        "guidance": (
            text_value(value["guidance"], field="guidance")
            if "guidance" in value
            else ""
        ),
    }
    if "finding_handoff" in value:
        try:
            handoff = QualityFindingHandoff.from_dict(value["finding_handoff"])
        except (QualityFindingHandoffError, TypeError, ValueError) as error:
            raise AgentRequestError(str(error)) from error
        if arguments["context_name"] is not None or arguments["memory_selectors"]:
            raise AgentRequestError(
                "finding_handoff cannot be combined with context_name or "
                "memory_selectors."
            )
        arguments["finding_handoff"] = handoff
    if kind == "apply":
        arguments.update(
            decisions=_decisions(value["decisions"]),
            expected_revision=text_value(
                value["expected_revision"],
                field="expected_revision",
            ),
        )
    return kind, arguments


def _analysis_result(result: ResolveAnalysisResult) -> JsonObject:
    return {
        "context_name": result.context_name,
        "context_uid": result.context_uid,
        "revision": result.revision,
        "status": result.status,
        "question": result.question,
        "requested_effects": list(result.requested_effects),
        "allowed_effects": list(result.allowed_effects),
        "denied_effects": list(result.denied_effects),
        "issues": [
            {
                "uid": issue.uid,
                "audit_key": issue.audit_key,
                "kind": issue.kind,
                "classification": issue.classification,
                "memory_uids": list(issue.memory_uids),
                "proposed_direction": issue.proposed_direction,
                "reason": issue.reason,
                "question": issue.question,
            }
            for issue in result.issues
        ],
        "effect": "NONE",
    }


def _apply_result(result: ResolveApplyResult) -> JsonObject:
    return {
        "context_name": result.context_name,
        "context_uid": result.context_uid,
        "revision": result.revision,
        "plan_uid": result.plan_uid,
        "checkpoint_uid": result.checkpoint_uid,
        "created_uids": list(result.created_uids),
        "updated_uids": list(result.updated_uids),
        "deleted_uids": list(result.deleted_uids),
        "unresolved_issue_uids": list(result.unresolved_issue_uids),
        "effect": "CHECKPOINT",
    }


_PUBLIC_ERRORS: tuple[tuple[type[SemanticError], str, str, bool], ...] = (
    (SemanticInputError, "invalid_request", "The Resolve request is invalid.", False),
    (
        SemanticContextError,
        "context_unavailable",
        "The Resolve Context is unavailable.",
        False,
    ),
    (
        SemanticAuthorityError,
        "authority_denied",
        "Resolve authority was denied.",
        False,
    ),
    (
        SemanticProviderFailure,
        "provider_failure",
        "The Resolve provider failed.",
        True,
    ),
    (
        SemanticConflictError,
        "concurrent_update",
        "The Resolve frame or finalized decisions changed.",
        False,
    ),
    (
        SemanticStorageError,
        "storage_failure",
        "Resolve storage failed safely.",
        False,
    ),
    (
        SemanticExecutionError,
        "execution_failed",
        "Resolve failed before publishing a complete outcome.",
        False,
    ),
)


class ResolveAgentAdapter:
    """Expose complete-Audit decisions and next-turn Update-backed Apply."""

    def __init__(self, client: MemCommitClient) -> None:
        if not isinstance(client, MemCommitClient):
            raise TypeError("ResolveAgentAdapter requires a MemCommitClient.")
        self._client = client
        self._analyses: dict[
            str,
            tuple[ResolveAnalysisResult, dict[str, object]],
        ] = {}

    @staticmethod
    def _matches_cached_request(
        analysis: ResolveAnalysisResult,
        analyzed_arguments: dict[str, object],
        apply_arguments: dict[str, object],
    ) -> bool:
        analyzed_context = analyzed_arguments.get("context_name")
        apply_context = apply_arguments.get("context_name")
        context_matches = apply_context in {
            analyzed_context,
            analysis.context_name,
        }
        return context_matches and all(
            analyzed_arguments.get(field) == apply_arguments.get(field)
            for field in (
                "memory_selectors",
                "allow_create",
                "allow_delete",
                "guidance",
                "finding_handoff",
            )
        )

    def _remember(
        self,
        analysis: ResolveAnalysisResult,
        arguments: dict[str, object],
    ) -> None:
        if analysis.issues:
            self._analyses[analysis.revision] = (analysis, dict(arguments))
        while len(self._analyses) > RESOLVE_AGENT_ANALYSIS_CACHE_LIMIT:
            # The cache is a short next-turn bridge, not a durable session log.
            self._analyses.pop(next(iter(self._analyses)))

    def invoke(self, payload: object) -> JsonObject:
        kind: ResolveAgentKind | None = None
        if isinstance(payload, Mapping) and payload.get("kind") in {
            "analyze",
            "apply",
        }:
            kind = payload["kind"]  # type: ignore[assignment]
        try:
            kind, arguments = _parse_request(payload)
        except AgentRequestError as error:
            return error_response(
                version=RESOLVE_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="invalid_request",
                message=str(error),
                retryable=False,
            )
        try:
            decisions = arguments.pop("decisions", ())
            expected_revision = arguments.pop("expected_revision", None)
            cached = (
                self._analyses.get(expected_revision)
                if isinstance(expected_revision, str)
                else None
            )
            request_arguments = dict(arguments)
            if (
                kind == "apply"
                and cached is not None
                and self._matches_cached_request(
                    cached[0], cached[1], request_arguments
                )
            ):
                result = _apply_result(
                    self._client.apply_resolve(
                        cached[0],
                        decisions=decisions,
                    )
                )
                self._analyses.pop(expected_revision, None)
                return {
                    "version": RESOLVE_AGENT_CONTRACT_VERSION,
                    "ok": True,
                    "kind": kind,
                    "result": result,
                }
            finding_handoff = arguments.pop("finding_handoff", None)
            if isinstance(finding_handoff, QualityFindingHandoff):
                arguments.pop("context_name", None)
                arguments.pop("memory_selectors", None)
            analysis = (
                self._client.resolve_conflict_finding(
                    finding_handoff,
                    **arguments,
                    expected_revision=expected_revision,
                )
                if isinstance(finding_handoff, QualityFindingHandoff)
                else self._client.resolve_context(
                    **arguments,
                    expected_revision=expected_revision,
                )
            )
            if kind == "analyze":
                self._remember(analysis, request_arguments)
                result = _analysis_result(analysis)
            else:
                result = _apply_result(
                    self._client.apply_resolve(
                        analysis,
                        decisions=decisions,
                    )
                )
        except SemanticError as error:
            for error_type, code, message, retryable in _PUBLIC_ERRORS:
                if isinstance(error, error_type):
                    return error_response(
                        version=RESOLVE_AGENT_CONTRACT_VERSION,
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
                version=RESOLVE_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="resolve_failed",
                message="Resolve failed without a more specific public category.",
                retryable=False,
            )
        except Exception:
            return error_response(
                version=RESOLVE_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="internal_error",
                message="The Resolve tool failed internally.",
                retryable=False,
            )
        return {
            "version": RESOLVE_AGENT_CONTRACT_VERSION,
            "ok": True,
            "kind": kind,
            "result": result,
        }


def resolve_agent_tool_schema() -> JsonObject:
    """Return the strict Resolve analyze/next-turn-Apply union schema."""

    text = {"type": "string", "minLength": 1, "pattern": r".*\S.*"}
    return {
        "name": RESOLVE_AGENT_TOOL_NAME,
        "description": (
            "Load or run one complete Context Audit, derive a conservative direction "
            "for every Audit item, then apply one decision per item on the next turn. "
            "Resolve turns accepted directions and exact intent into a process-local "
            "Source; the ordinary Update planner generates one whole-Context plan."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["version", "kind"],
            "properties": {
                "version": {
                    "type": "integer",
                    "const": RESOLVE_AGENT_CONTRACT_VERSION,
                },
                "kind": {"type": "string", "enum": ["analyze", "apply"]},
                "context_name": {"type": ["string", "null"], "minLength": 1},
                "memory_selectors": {"type": "array", "items": text},
                "allow_create": {"type": "boolean", "default": True},
                "allow_delete": {"type": "boolean", "default": False},
                "guidance": text,
                "finding_handoff": quality_finding_handoff_agent_schema(),
                "decisions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["issue_uid", "kind"],
                        "properties": {
                            "issue_uid": text,
                            "kind": {
                                "type": "string",
                                "enum": ["CONFIRM", "INTENT", "FORCE"],
                            },
                            "intent": text,
                        },
                    },
                },
                "expected_revision": text,
            },
        },
    }


__all__ = [
    "RESOLVE_AGENT_CONTRACT_VERSION",
    "RESOLVE_AGENT_TOOL_NAME",
    "ResolveAgentAdapter",
    "ResolveAgentKind",
    "resolve_agent_tool_schema",
]
