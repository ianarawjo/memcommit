"""Versioned JSON-safe agent adapter for the complete structural Atomize flow."""

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
    AtomizeReviewedApplyResult,
    AtomizeSaveAsApplyResult,
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
AtomizeAgentKind = Literal[
    "open",
    "respond",
    "plan_output",
    "reanalyze",
    "apply_as_is",
    "save_as",
    "incorporate_and_apply",
]
_KINDS = {
    "open",
    "respond",
    "plan_output",
    "reanalyze",
    "apply_as_is",
    "save_as",
    "incorporate_and_apply",
}


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
    if kind not in _KINDS:
        raise AgentRequestError(
            "kind must be one of: open, respond, plan_output, reanalyze, "
            "apply_as_is, save_as, incorporate_and_apply."
        )
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


def _comment(value: object) -> str:
    if not isinstance(value, str):
        raise AgentRequestError("comment must be text, including empty text to clear.")
    if len(value) > 20_000:
        raise AgentRequestError("comment exceeds the 20000-character limit.")
    return value


def _versioned_arguments(value: Mapping[str, object]) -> dict[str, object]:
    return {
        "context_name": _context_name(value),
        "expected_version": _expected_version(value["expected_version"]),
    }


def _parse_request(payload: object) -> tuple[AtomizeAgentKind, dict[str, object]]:
    value = object_value(payload, label="Atomize request")
    kind = _kind(value)
    if kind == "open":
        exact_fields(
            value,
            required={"version", "kind"},
            optional=frozenset(
                {"context_name", "refresh", "use_prepared", "memory_selector"}
            ),
            label="Atomize open request",
        )
        return kind, {
            "context_name": _context_name(value),
            "refresh": _boolean(value.get("refresh", False), field="refresh"),
            "use_prepared": _boolean(
                value.get("use_prepared", True),
                field="use_prepared",
            ),
            "memory_selector": text_value(
                value.get("memory_selector"),
                field="memory_selector",
                optional=True,
            ),
        }
    if kind == "respond":
        exact_fields(
            value,
            required={
                "version",
                "kind",
                "expected_version",
                "issue_uid",
                "option_uid",
                "comment",
            },
            optional=frozenset({"context_name"}),
            label="Atomize respond request",
        )
        return kind, {
            **_versioned_arguments(value),
            "issue_uid": text_value(value["issue_uid"], field="issue_uid"),
            "option_uid": text_value(
                value["option_uid"],
                field="option_uid",
                optional=True,
            ),
            "comment": _comment(value["comment"]),
        }
    if kind == "plan_output":
        exact_fields(
            value,
            required={"version", "kind", "expected_version", "output_context_name"},
            optional=frozenset({"context_name"}),
            label="Atomize plan_output request",
        )
        return kind, {
            **_versioned_arguments(value),
            "output_context_name": text_value(
                value["output_context_name"],
                field="output_context_name",
            ),
        }
    exact_fields(
        value,
        required={"version", "kind", "expected_version"},
        optional=frozenset({"context_name"}),
        label=f"Atomize {kind} request",
    )
    return kind, _versioned_arguments(value)


def _analysis_result(
    result: AtomizeAnalysisResult,
    *,
    effect: str | None = None,
) -> JsonObject:
    provider_used = result.origin == "PROVIDER"
    cache_used = result.origin in {"SAVED", "EXACT_PREWARM"}
    projected: JsonObject = {
        "analysis_uid": result.analysis_uid,
        "version": result.version,
        "origin": result.origin,
        "provider_used": provider_used,
        "cache_used": cache_used,
        "effect": effect or (
            "NONE" if result.origin == "SAVED" else "DERIVED_SESSION"
        ),
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
                "selected_reading_uid": issue.selected_reading_uid,
                "response_text": issue.response_text,
            }
            for issue in result.issues
        ],
        "workbench_uid": result.workbench_uid,
        "output_context_name": result.output_context_name,
        "review_edit_allowed": result.review_edit_allowed,
        "response_reanalysis_allowed": result.response_reanalysis_allowed,
        "application_completed": result.application_completed,
        "in_place_apply_allowed": result.in_place_apply_allowed,
    }
    projected["actions"] = {
        "respond": {
            "allowed": result.review_edit_allowed,
            "expected_version": result.version,
            "provider_used": False,
            "effect": "DERIVED_SESSION",
        },
        "plan_output": {
            "allowed": result.review_edit_allowed,
            "expected_version": result.version,
            "provider_used": False,
            "effect": "DERIVED_SESSION",
        },
        "reanalyze": {
            "allowed": result.response_reanalysis_allowed,
            "expected_version": result.version,
            "provider_used": True,
            "effect": "DERIVED_SESSION",
        },
        "apply_as_is": {
            "allowed": (
                result.in_place_apply_allowed and not result.application_completed
            ),
            "expected_version": result.version,
            "provider_used": True,
            "effect": "CONTEXT_CHECKPOINT",
        },
        "save_as": {
            "allowed": (
                not result.in_place_apply_allowed and not result.application_completed
            ),
            "expected_version": result.version,
            "provider_used": True,
            "effect": "CONTEXT_CHECKPOINT",
        },
        "incorporate_and_apply": {
            "allowed": result.response_reanalysis_allowed,
            "expected_version": result.version,
            "provider_used": True,
            "effect": "CONTEXT_CHECKPOINT",
        },
    }
    # Preserve the original small key for version-1 consumers while extending
    # the same contract with the complete action map above.
    projected["apply_as_is"] = projected["actions"]["apply_as_is"]
    return projected


def _lineage_items(result) -> list[JsonObject]:
    return [
        {
            "source_memory_uid": item.source_memory_uid,
            "classification": item.classification,
            "result_memory_uids": list(item.result_memory_uids),
            "result_contents": list(item.result_contents),
            "reason": item.reason,
            "reason_codes": list(item.reason_codes),
        }
        for item in result.items
    ]


def _apply_result(
    result: AtomizeStructuralApplyResult | AtomizeSaveAsApplyResult,
) -> JsonObject:
    value: JsonObject = {
        "analysis_uid": result.analysis_uid,
        "context_uid": result.context_uid,
        "context_name": result.context_name,
        "checkpoint_uid": result.checkpoint_uid,
        "split_count": result.split_count,
        "child_count": result.child_count,
        "preserved_count": result.preserved_count,
        "dedun_group_count": result.dedun_group_count,
        "absorbed_count": result.absorbed_count,
        "normal_form_verified": result.normal_form_verified,
        "application_mode": result.application_mode,
        "unresolved_at_apply_count": result.unresolved_at_apply_count,
        "items": _lineage_items(result),
        "recovered": result.recovered,
        "provider_used": not result.recovered,
        "effect": "CONTEXT_CHECKPOINT",
        "created_context": isinstance(result, AtomizeSaveAsApplyResult),
    }
    if isinstance(result, AtomizeSaveAsApplyResult):
        value.update(
            {
                "source_context_uid": result.source_context_uid,
                "source_context_name": result.source_context_name,
                "current_context_name": result.current_context_name,
            }
        )
    return value


_PUBLIC_ERRORS: tuple[tuple[type[AtomizeError], str, str, bool], ...] = (
    (AtomizeInputError, "invalid_request", "The Atomize request is invalid.", False),
    (
        AtomizeContextError,
        "context_unavailable",
        "The Atomize Context or saved analysis is unavailable.",
        False,
    ),
    (AtomizeProviderFailure, "provider_failure", "The Atomize provider failed.", True),
    (
        AtomizeConflictError,
        "stale_state",
        "The accepted Atomize revision changed.",
        False,
    ),
    (AtomizeStorageError, "storage_failure", "Atomize storage failed safely.", False),
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
        if isinstance(payload, Mapping) and payload.get("kind") in _KINDS:
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
                projected = _analysis_result(
                    self._client.open_atomize_analysis(**arguments)
                )
            elif kind == "respond":
                update = self._client.update_atomize_response(**arguments)
                projected = {
                    "update_kind": update.kind,
                    "changed": update.changed,
                    "proposal": _analysis_result(
                        update.proposal,
                        effect="DERIVED_SESSION" if update.changed else "NONE",
                    ),
                }
            elif kind == "plan_output":
                update = self._client.plan_atomize_output(**arguments)
                projected = {
                    "update_kind": update.kind,
                    "changed": update.changed,
                    "proposal": _analysis_result(
                        update.proposal,
                        effect="DERIVED_SESSION" if update.changed else "NONE",
                    ),
                }
            elif kind == "reanalyze":
                projected = _analysis_result(
                    self._client.reanalyze_atomize_responses(**arguments)
                )
            elif kind == "apply_as_is":
                projected = _apply_result(
                    self._client.apply_saved_atomize_as_is(**arguments)
                )
            elif kind == "save_as":
                projected = _apply_result(
                    self._client.save_saved_atomize_as(**arguments)
                )
            else:
                reviewed: AtomizeReviewedApplyResult = (
                    self._client.incorporate_and_apply_atomize(**arguments)
                )
                projected = {
                    "proposal": _analysis_result(reviewed.proposal),
                    "application": _apply_result(reviewed.application),
                    "provider_used": True,
                    "effect": "CONTEXT_CHECKPOINT",
                }
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
    """Return the strict complete structural Atomize lifecycle schema."""

    text = {"type": "string", "minLength": 1, "pattern": r".*\S.*"}
    nullable_text = {**text, "type": ["string", "null"]}
    version = {"type": "integer", "const": ATOMIZE_AGENT_CONTRACT_VERSION}
    expected = {
        "type": "string",
        "pattern": "^[0-9a-f]{64}$",
        "description": "Opaque version returned by the exact reviewed action.",
    }

    def base(kind: AtomizeAgentKind) -> JsonObject:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["version", "kind", "expected_version"],
            "properties": {
                "version": version,
                "kind": {"type": "string", "const": kind},
                "context_name": nullable_text,
                "expected_version": expected,
            },
        }

    open_request: JsonObject = {
        "type": "object",
        "additionalProperties": False,
        "required": ["version", "kind"],
        "properties": {
            "version": version,
            "kind": {"type": "string", "const": "open"},
            "context_name": nullable_text,
            "memory_selector": nullable_text,
            "refresh": {"type": "boolean", "default": False},
            "use_prepared": {"type": "boolean", "default": True},
        },
    }
    respond = base("respond")
    respond["required"] = [
        "version",
        "kind",
        "expected_version",
        "issue_uid",
        "option_uid",
        "comment",
    ]
    respond["properties"] = {
        **respond["properties"],
        "issue_uid": text,
        "option_uid": nullable_text,
        "comment": {"type": "string", "maxLength": 20_000},
    }
    plan_output = base("plan_output")
    plan_output["required"] = [
        "version",
        "kind",
        "expected_version",
        "output_context_name",
    ]
    plan_output["properties"] = {
        **plan_output["properties"],
        "output_context_name": text,
    }
    return {
        "name": ATOMIZE_AGENT_TOOL_NAME,
        "description": (
            "Open a whole-Context or focused structural Atomize review; edit "
            "exact responses and Output plans; incorporate unary responses; "
            "then apply in place or publish the reviewed require-new Save As. "
            "Every saved action is version-bound. Reanalysis uses the provider; "
            "review edits do not, while final application runs normal-form "
            "verification before publication."
        ),
        "parameters": {
            "type": "object",
            "oneOf": [
                open_request,
                respond,
                plan_output,
                base("reanalyze"),
                base("apply_as_is"),
                base("save_as"),
                base("incorporate_and_apply"),
            ],
        },
    }


__all__ = [
    "ATOMIZE_AGENT_CONTRACT_VERSION",
    "ATOMIZE_AGENT_TOOL_NAME",
    "AtomizeAgentAdapter",
    "AtomizeAgentKind",
    "atomize_agent_tool_schema",
]
