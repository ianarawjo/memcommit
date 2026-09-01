"""Versioned JSON-safe agent adapter for the public Meld facade."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from memcommit.adapters.python_api import (
    MeldAuthorityError,
    MeldConflictError,
    MeldContextError,
    MeldError,
    MeldExecutionError,
    MeldInputError,
    MeldProviderFailure,
    MeldDecisionInput,
    MeldSessionResult,
    MeldStorageError,
    MemCommitClient,
)
from memcommit.adapters.agent.contract import (
    AgentRequestError,
    JsonObject,
    error_response,
    exact_fields,
    object_value,
    text_value,
)


MELD_AGENT_CONTRACT_VERSION = 1
MELD_AGENT_TOOL_NAME = "memcommit_meld"
MeldAgentKind = Literal[
    "start",
    "restart",
    "open",
    "resolve",
]


def _boolean(value: object, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise AgentRequestError(f"{field} must be a boolean.")
    return value


def _base(value: Mapping[str, object]) -> MeldAgentKind:
    version = value.get("version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != MELD_AGENT_CONTRACT_VERSION
    ):
        raise AgentRequestError(
            f"version must be exactly {MELD_AGENT_CONTRACT_VERSION}."
        )
    kind = value.get("kind")
    if kind not in {
        "start",
        "restart",
        "open",
        "resolve",
    }:
        raise AgentRequestError(
            "kind must be one of: start, restart, open, resolve."
        )
    return kind  # type: ignore[return-value]


def _parse_request(payload: object) -> tuple[MeldAgentKind, dict[str, object]]:
    value = object_value(payload, label="Meld request")
    kind = _base(value)
    if kind == "start":
        exact_fields(
            value,
            required={"version", "kind", "left_context", "right_context"},
            optional=frozenset(
                {
                    "mode",
                    "target_context",
                    "create_target",
                    "left_descendants",
                    "right_descendants",
                }
            ),
            label="Meld start request",
        )
        return kind, {
            "left_context": text_value(value["left_context"], field="left_context"),
            "right_context": text_value(
                value["right_context"],
                field="right_context",
            ),
            "mode": text_value(value.get("mode", "directional"), field="mode"),
            "target_context": text_value(
                value.get("target_context"),
                field="target_context",
                optional=True,
            ),
            "create_target": _boolean(
                value.get("create_target", False),
                field="create_target",
            ),
            "left_descendants": _boolean(
                value.get("left_descendants", False),
                field="left_descendants",
            ),
            "right_descendants": _boolean(
                value.get("right_descendants", False),
                field="right_descendants",
            ),
        }
    if kind == "resolve":
        exact_fields(
            value,
            required={
                "version",
                "kind",
                "target_context",
                "expected_version",
                "decisions",
            },
            label="Meld resolve request",
        )
        raw_decisions = value["decisions"]
        if not isinstance(raw_decisions, list):
            raise AgentRequestError("decisions must be a list.")
        decisions: list[MeldDecisionInput] = []
        for index, raw in enumerate(raw_decisions):
            decision = object_value(raw, label=f"Meld decision {index + 1}")
            exact_fields(
                decision,
                required={"issue_uid", "kind"},
                optional={"intent"},
                label=f"Meld decision {index + 1}",
            )
            decision_kind = text_value(decision["kind"], field="decision kind")
            if decision_kind not in {"confirm", "intent", "force"}:
                raise AgentRequestError(
                    "Meld decision kind must be confirm, intent, or force."
                )
            try:
                decisions.append(
                    MeldDecisionInput(
                        issue_uid=text_value(
                            decision["issue_uid"], field="decision issue_uid"
                        ),
                        kind=decision_kind,  # type: ignore[arg-type]
                        intent=(
                            text_value(decision["intent"], field="decision intent")
                            if "intent" in decision
                            else ""
                        ),
                    )
                )
            except (TypeError, ValueError) as error:
                raise AgentRequestError(str(error)) from error
        return kind, {
            "target_context": text_value(
                value["target_context"],
                field="target_context",
            ),
            "expected_version": text_value(
                value["expected_version"], field="expected_version"
            ),
            "decisions": tuple(decisions),
        }
    if kind == "restart":
        exact_fields(
            value,
            required={
                "version",
                "kind",
                "left_context",
                "right_context",
                "target_context",
                "expected_version",
            },
            optional=frozenset({"mode", "left_descendants", "right_descendants"}),
            label="Meld restart request",
        )
        return kind, {
            "left_context": text_value(value["left_context"], field="left_context"),
            "right_context": text_value(
                value["right_context"],
                field="right_context",
            ),
            "target_context": text_value(
                value["target_context"],
                field="target_context",
            ),
            "expected_version": text_value(
                value["expected_version"],
                field="expected_version",
            ),
            "mode": text_value(value.get("mode", "directional"), field="mode"),
            "left_descendants": _boolean(
                value.get("left_descendants", False),
                field="left_descendants",
            ),
            "right_descendants": _boolean(
                value.get("right_descendants", False),
                field="right_descendants",
            ),
        }
    if kind == "open":
        exact_fields(
            value,
            required={"version", "kind", "target_context"},
            label="Meld open request",
        )
        return kind, {
            "target_context": text_value(
                value["target_context"],
                field="target_context",
            )
        }
    raise AssertionError("Unhandled Meld agent action.")


def _session_result(result: MeldSessionResult) -> JsonObject:
    return {
        "session_uid": result.session_uid,
        "version": result.version,
        "mode": result.mode,
        "state": result.state,
        "left_context": result.left_context,
        "right_context": result.right_context,
        "target_context": result.target_context,
        "turn_count": result.turn_count,
        "overview": result.overview,
        "ready_to_apply": result.ready_to_apply,
        "origin": result.origin,
        "checkpoint_uid": result.checkpoint_uid,
        "unresolved_count": result.unresolved_count,
        "issues": [
            {
                "uid": issue.uid,
                "priority": issue.priority,
                "title": issue.title,
                "question": issue.question,
                "why_it_matters": issue.why_it_matters,
                "options": [
                    {"uid": option.uid, "label": option.label, "text": option.text}
                    for option in issue.options
                ],
            }
            for issue in result.issues
        ],
        "proposals": [
            {
                "uid": proposal.uid,
                "operation": proposal.operation,
                "disposition": proposal.disposition,
                "content": proposal.content,
                "reason": proposal.reason,
            }
            for proposal in result.proposals
        ],
    }


_PUBLIC_ERRORS: tuple[tuple[type[MeldError], str, str, bool], ...] = (
    (MeldInputError, "invalid_request", "The Meld request is invalid.", False),
    (MeldContextError, "context_unavailable", "A Meld Context is unavailable.", False),
    (MeldAuthorityError, "authority_denied", "Meld authority was denied.", False),
    (MeldProviderFailure, "provider_failure", "The Meld provider failed.", True),
    (MeldConflictError, "concurrent_update", "The Meld changed concurrently.", False),
    (MeldStorageError, "storage_failure", "Meld storage failed safely.", False),
    (MeldExecutionError, "execution_failed", "Meld execution failed.", False),
)


class MeldAgentAdapter:
    """Translate one exact JSON action to one public Meld call."""

    def __init__(self, client: MemCommitClient) -> None:
        if not isinstance(client, MemCommitClient):
            raise TypeError("MeldAgentAdapter requires a MemCommitClient.")
        self._client = client

    def invoke(self, payload: object) -> JsonObject:
        kind: MeldAgentKind | None = None
        if isinstance(payload, Mapping) and payload.get("kind") in {
            "start",
            "restart",
            "open",
            "resolve",
        }:
            kind = payload["kind"]  # type: ignore[assignment]
        try:
            kind, arguments = _parse_request(payload)
        except AgentRequestError as error:
            return error_response(
                version=MELD_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="invalid_request",
                message=str(error),
                retryable=False,
            )
        try:
            method = getattr(self._client, f"{kind}_meld")
            result = method(**arguments)
        except MeldError as error:
            for error_type, code, message, retryable in _PUBLIC_ERRORS:
                if isinstance(error, error_type):
                    return error_response(
                        version=MELD_AGENT_CONTRACT_VERSION,
                        kind=kind,
                        code=code,
                        message=(
                            str(error)
                            if isinstance(
                                error,
                                (MeldInputError, MeldContextError, MeldAuthorityError),
                            )
                            else message
                        ),
                        retryable=retryable,
                    )
            return error_response(
                version=MELD_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="meld_failed",
                message="Meld failed without a more specific public category.",
                retryable=False,
            )
        except Exception:
            return error_response(
                version=MELD_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="internal_error",
                message="The Meld tool failed internally.",
                retryable=False,
            )
        return {
            "version": MELD_AGENT_CONTRACT_VERSION,
            "ok": True,
            "kind": kind,
            "result": {
                "session": _session_result(result),
            },
        }


def meld_agent_tool_schema() -> JsonObject:
    """Return one strict union schema for versioned Meld actions."""

    text = {"type": "string", "minLength": 1, "pattern": r".*\S.*"}
    kinds = ["start", "restart", "open", "resolve"]
    return {
        "name": MELD_AGENT_TOOL_NAME,
        "description": (
            "Start, inspect, or resolve a candidate-based MemCommit Meld. Resolve "
            "submits one decision per Audit item, runs one whole-candidate Update, "
            "re-audits it, and applies only a verified post-image."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["version", "kind"],
            "properties": {
                "version": {"type": "integer", "const": 1},
                "kind": {"type": "string", "enum": kinds},
                "left_context": text,
                "right_context": text,
                "target_context": {"type": ["string", "null"], "minLength": 1},
                "expected_version": {
                    **text,
                    "description": (
                        "Opaque version returned by open; required by restart "
                        "and resolve."
                    ),
                },
                "mode": {"type": "string", "enum": ["directional", "symmetric"]},
                "create_target": {"type": "boolean"},
                "left_descendants": {"type": "boolean"},
                "right_descendants": {"type": "boolean"},
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
                                "enum": ["confirm", "intent", "force"],
                            },
                            "intent": {"type": "string"},
                        },
                    },
                },
            },
            "allOf": [
                {
                    "if": {"properties": {"kind": {"const": "resolve"}}},
                    "then": {
                        "required": [
                            "target_context",
                            "expected_version",
                            "decisions",
                        ]
                    },
                }
            ],
        },
    }


__all__ = [
    "MELD_AGENT_CONTRACT_VERSION",
    "MELD_AGENT_TOOL_NAME",
    "MeldAgentAdapter",
    "MeldAgentKind",
    "meld_agent_tool_schema",
]
