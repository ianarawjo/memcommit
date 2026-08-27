"""Versioned JSON-safe agent adapter for exact Resolve analysis and Apply."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from memcommit.adapters.python_api import (
    MemCommitClient,
    ResolveAnalysisResult,
    ResolveApplyResult,
    SemanticAuthorityError,
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
from memcommit.interfaces.agent.quality_find import (
    quality_finding_handoff_agent_schema,
)
from memcommit.application.reviewing.quality.handoff import (
    QualityFindingHandoff,
    QualityFindingHandoffError,
)


RESOLVE_AGENT_CONTRACT_VERSION = 2
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
        "target_fit",
        "finding_handoff",
    }
    required = {"version", "kind"}
    optional = common
    if kind == "apply":
        required |= {"candidate_uid", "expected_revision"}
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
        "target_fit": value.get("target_fit", "MAY"),
    }
    if arguments["target_fit"] not in {"MAY", "YES"}:
        raise AgentRequestError("target_fit must be MAY or YES.")
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
            candidate_uid=text_value(value["candidate_uid"], field="candidate_uid"),
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
        "initial_fit": result.initial_fit,
        "initial_fit_reason": result.initial_fit_reason,
        "question": result.question,
        "target_fit": result.target_fit,
        "requested_effects": list(result.requested_effects),
        "allowed_effects": list(result.allowed_effects),
        "denied_effects": list(result.denied_effects),
        "candidates": [
            {
                "uid": candidate.uid,
                "summary": candidate.summary,
                "classification": candidate.classification,
                "resolution_level": candidate.resolution_level,
                "rule_ids": list(candidate.rule_ids),
                "grounded": candidate.grounded,
                "issues": [
                    {
                        "uid": issue.uid,
                        "kind": issue.kind,
                        "memory_uids": list(issue.memory_uids),
                        "selected_interpretation": issue.selected_interpretation,
                        "basis_memory_uids": list(issue.basis_memory_uids),
                        "assumptions": list(issue.assumptions),
                        "reason": issue.reason,
                    }
                    for issue in candidate.issues
                ],
                "cost": {
                    "deletes": candidate.deletes,
                    "creates": candidate.creates,
                    "updates": candidate.updates,
                    "changed_units": candidate.changed_units,
                },
                "verification_reason": candidate.verification_reason,
                "fit_verdict": candidate.fit_verdict,
                "fit_reason": candidate.fit_reason,
                "effects": [
                    {
                        "kind": effect.kind,
                        "memory_uid": effect.memory_uid,
                        "before": effect.before,
                        "after": effect.after,
                        "source_memory_uids": list(effect.source_memory_uids),
                        "reason": effect.reason,
                    }
                    for effect in candidate.effects
                ],
            }
            for candidate in result.candidates
        ],
        "effect": "NONE",
    }


def _apply_result(result: ResolveApplyResult) -> JsonObject:
    return {
        "context_name": result.context_name,
        "context_uid": result.context_uid,
        "revision": result.revision,
        "candidate_uid": result.candidate_uid,
        "checkpoint_uid": result.checkpoint_uid,
        "created_uids": list(result.created_uids),
        "updated_uids": list(result.updated_uids),
        "deleted_uids": list(result.deleted_uids),
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
        "The Resolve frame or exact candidate changed.",
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
    """Expose analysis and next-turn exact Apply through one agent tool.

    A verified grounded analysis is retained only in this adapter process.  A
    following Apply can therefore use the exact typed plan the agent already
    showed instead of asking a nondeterministic provider to reproduce it.
    Stateless replay remains the fail-closed fallback after process restart.
    """

    def __init__(self, client: MemCommitClient) -> None:
        if not isinstance(client, MemCommitClient):
            raise TypeError("ResolveAgentAdapter requires a MemCommitClient.")
        self._client = client
        self._analyses: dict[
            tuple[str, str],
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
                "target_fit",
                "finding_handoff",
            )
        )

    def _remember(
        self,
        analysis: ResolveAnalysisResult,
        arguments: dict[str, object],
    ) -> None:
        for candidate in analysis.candidates:
            self._analyses[(analysis.revision, candidate.uid)] = (
                analysis,
                dict(arguments),
            )
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
            candidate_uid = arguments.pop("candidate_uid", None)
            expected_revision = arguments.pop("expected_revision", None)
            cached = (
                self._analyses.get((expected_revision, candidate_uid))
                if isinstance(expected_revision, str) and isinstance(candidate_uid, str)
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
                cached_candidate = next(
                    candidate
                    for candidate in cached[0].candidates
                    if candidate.uid == candidate_uid
                )
                if not cached_candidate.grounded:
                    raise SemanticInputError(
                        "An ASSUMED Resolve interpretation is process-local "
                        "working context and cannot be applied."
                    )
                result = _apply_result(
                    self._client.apply_resolve(
                        cached[0],
                        candidate_uid=candidate_uid,
                    )
                )
                self._analyses.pop((expected_revision, candidate_uid), None)
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
                assert isinstance(candidate_uid, str)
                if not any(
                    candidate.uid == candidate_uid for candidate in analysis.candidates
                ):
                    raise SemanticConflictError(
                        "The reviewed Resolve candidate was not regenerated."
                    )
                result = _apply_result(
                    self._client.apply_resolve(
                        analysis,
                        candidate_uid=candidate_uid,
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
            "Analyze one complete exact Context for one automatic grounded or "
            "assumed Issue interpretation plan, "
            "or apply that exact typed plan on the next turn using its revision "
            "and candidate UID; a restarted process falls back to fail-closed "
            "regeneration. UPDATE and CREATE are enabled by default; "
            "DELETE requires explicit opt-in and grounding guidance. ASSUMED plans "
            "are process-local and cannot be applied."
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
                "target_fit": {
                    "type": "string",
                    "enum": ["MAY", "YES"],
                    "default": "MAY",
                },
                "finding_handoff": quality_finding_handoff_agent_schema(),
                "candidate_uid": text,
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
