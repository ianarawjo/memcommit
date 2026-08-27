"""Versioned agent adapter for conversational Atomize Grounding."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from memcommit.adapters.python_api import (
    AtomizeGroundingApplyResult,
    AtomizeGroundingConflictError,
    AtomizeGroundingContextError,
    AtomizeGroundingError,
    AtomizeGroundingExecutionError,
    AtomizeGroundingInputError,
    AtomizeGroundingProviderFailure,
    AtomizeGroundingSessionResult,
    AtomizeGroundingStorageError,
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


ATOMIZE_GROUNDING_AGENT_CONTRACT_VERSION = 1
ATOMIZE_GROUNDING_AGENT_TOOL_NAME = "memcommit_atomize_grounding"
AtomizeGroundingAgentKind = Literal["open", "start", "reply", "keep", "apply"]


def _kind(value: Mapping[str, object]) -> AtomizeGroundingAgentKind:
    version = value.get("version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != ATOMIZE_GROUNDING_AGENT_CONTRACT_VERSION
    ):
        raise AgentRequestError(
            f"version must be exactly {ATOMIZE_GROUNDING_AGENT_CONTRACT_VERSION}."
        )
    kind = value.get("kind")
    if kind not in {"open", "start", "reply", "keep", "apply"}:
        raise AgentRequestError("kind must be one of: open, start, reply, keep, apply.")
    return kind  # type: ignore[return-value]


def _context_name(value: Mapping[str, object]) -> str | None:
    return text_value(
        value.get("context_name"),
        field="context_name",
        optional=True,
    )


def _parse_request(
    payload: object,
) -> tuple[AtomizeGroundingAgentKind, dict[str, object]]:
    value = object_value(payload, label="Atomize Grounding request")
    kind = _kind(value)
    if kind == "start":
        exact_fields(
            value,
            required={"version", "kind", "selector", "comment"},
            optional=frozenset({"context_name"}),
            label="Atomize Grounding start request",
        )
        return kind, {
            "selector": text_value(value["selector"], field="selector"),
            "comment": text_value(value["comment"], field="comment"),
            "context_name": _context_name(value),
        }
    if kind == "reply":
        exact_fields(
            value,
            required={"version", "kind", "reply"},
            optional=frozenset({"context_name", "revision"}),
            label="Atomize Grounding reply request",
        )
        revision = text_value(
            value.get("revision", "EXTEND"),
            field="revision",
        )
        if revision.upper() not in {"CONFIRM", "EXTEND", "CORRECT", "RETRACT"}:
            raise AgentRequestError(
                "revision must be one of: CONFIRM, EXTEND, CORRECT, RETRACT."
            )
        return kind, {
            "reply": text_value(value["reply"], field="reply"),
            "context_name": _context_name(value),
            "revision": revision.upper(),
        }
    exact_fields(
        value,
        required={"version", "kind"},
        optional=frozenset({"context_name"}),
        label=f"Atomize Grounding {kind} request",
    )
    return kind, {"context_name": _context_name(value)}


def _session_result(result: AtomizeGroundingSessionResult) -> JsonObject:
    return {
        "session_uid": result.session_uid,
        "version": result.version,
        "context_name": result.context_name,
        "state": result.state,
        "issue_uid": result.issue_uid,
        "issue_kind": result.issue_kind,
        "arity": result.arity,
        "turn_count": result.turn_count,
        "active_understanding": list(result.active_understanding),
        "current_status": result.current_status,
        "current_explanation": result.current_explanation,
        "questions": [
            {
                "uid": question.uid,
                "kind": question.kind,
                "priority": question.priority,
                "text": question.text,
                "reason": question.reason,
                "issue_uids": list(question.issue_uids),
            }
            for question in result.questions
        ],
        "proposals": [
            {
                "uid": proposal.uid,
                "operation": proposal.operation,
                "necessity": proposal.necessity,
                "memory_uid": proposal.memory_uid,
                "content": proposal.content,
                "reason": proposal.reason,
                "issue_uids": list(proposal.issue_uids),
            }
            for proposal in result.proposals
        ],
        "ready_to_apply": result.ready_to_apply,
        "checkpoint_uid": result.checkpoint_uid,
    }


_PUBLIC_ERRORS: tuple[tuple[type[AtomizeGroundingError], str, str, bool], ...] = (
    (
        AtomizeGroundingInputError,
        "invalid_request",
        "The Atomize Grounding request is invalid.",
        False,
    ),
    (
        AtomizeGroundingContextError,
        "context_unavailable",
        "The Atomize Grounding Context or saved analysis is unavailable.",
        False,
    ),
    (
        AtomizeGroundingProviderFailure,
        "provider_failure",
        "The Atomize Grounding provider failed.",
        True,
    ),
    (
        AtomizeGroundingConflictError,
        "concurrent_update",
        "Atomize Grounding changed concurrently.",
        False,
    ),
    (
        AtomizeGroundingStorageError,
        "storage_failure",
        "Atomize Grounding storage failed safely.",
        False,
    ),
    (
        AtomizeGroundingExecutionError,
        "execution_failed",
        "Atomize Grounding failed before publishing a complete outcome.",
        False,
    ),
)


class AtomizeGroundingAgentAdapter:
    """Translate one exact JSON action to one public Grounding call."""

    def __init__(self, client: MemCommitClient) -> None:
        if not isinstance(client, MemCommitClient):
            raise TypeError("AtomizeGroundingAgentAdapter requires a MemCommitClient.")
        self._client = client

    def invoke(self, payload: object) -> JsonObject:
        kind: AtomizeGroundingAgentKind | None = None
        if isinstance(payload, Mapping) and payload.get("kind") in {
            "open",
            "start",
            "reply",
            "keep",
            "apply",
        }:
            kind = payload["kind"]  # type: ignore[assignment]
        try:
            kind, arguments = _parse_request(payload)
        except AgentRequestError as error:
            return error_response(
                version=ATOMIZE_GROUNDING_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="invalid_request",
                message=str(error),
                retryable=False,
            )

        try:
            method = getattr(self._client, f"{kind}_atomize_grounding")
            result = method(**arguments)
        except AtomizeGroundingError as error:
            for error_type, code, message, retryable in _PUBLIC_ERRORS:
                if isinstance(error, error_type):
                    return error_response(
                        version=ATOMIZE_GROUNDING_AGENT_CONTRACT_VERSION,
                        kind=kind,
                        code=code,
                        message=(
                            str(error)
                            if isinstance(
                                error,
                                (
                                    AtomizeGroundingInputError,
                                    AtomizeGroundingContextError,
                                ),
                            )
                            else message
                        ),
                        retryable=retryable,
                    )
            return error_response(
                version=ATOMIZE_GROUNDING_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="grounding_failed",
                message=(
                    "Atomize Grounding failed without a more specific public category."
                ),
                retryable=False,
            )
        except Exception:
            return error_response(
                version=ATOMIZE_GROUNDING_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="internal_error",
                message="The Atomize Grounding tool failed internally.",
                retryable=False,
            )

        apply_result = (
            result if isinstance(result, AtomizeGroundingApplyResult) else None
        )
        session = apply_result.session if apply_result is not None else result
        return {
            "version": ATOMIZE_GROUNDING_AGENT_CONTRACT_VERSION,
            "ok": True,
            "kind": kind,
            "result": {
                "session": _session_result(session),
                **(
                    {
                        "checkpoint_uid": apply_result.checkpoint_uid,
                        "change_count": apply_result.change_count,
                        "recovered": apply_result.recovered,
                    }
                    if apply_result is not None
                    else {}
                ),
            },
        }


def atomize_grounding_agent_tool_schema() -> JsonObject:
    """Return a strict union schema for the five Grounding lifecycle actions."""

    text = {"type": "string", "minLength": 1, "pattern": r".*\S.*"}
    nullable_text = {**text, "type": ["string", "null"]}
    version = {
        "type": "integer",
        "const": ATOMIZE_GROUNDING_AGENT_CONTRACT_VERSION,
    }

    def base(kind: AtomizeGroundingAgentKind) -> JsonObject:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["version", "kind"],
            "properties": {
                "version": version,
                "kind": {"type": "string", "const": kind},
                "context_name": nullable_text,
            },
        }

    start = base("start")
    start["required"] = ["version", "kind", "selector", "comment"]
    start["properties"] = {
        **start["properties"],
        "selector": text,
        "comment": text,
    }
    reply = base("reply")
    reply["required"] = ["version", "kind", "reply"]
    reply["properties"] = {
        **reply["properties"],
        "reply": text,
        "revision": {
            "type": "string",
            "enum": ["CONFIRM", "EXTEND", "CORRECT", "RETRACT"],
            "default": "EXTEND",
        },
    }
    return {
        "name": ATOMIZE_GROUNDING_AGENT_TOOL_NAME,
        "description": (
            "Open, start, continue, keep review-only, or apply one issue-scoped "
            "Atomize Grounding dialogue. Start and reply use the provider; "
            "open, keep, and apply do not."
        ),
        "parameters": {
            "type": "object",
            "oneOf": [base("open"), start, reply, base("keep"), base("apply")],
        },
    }


__all__ = [
    "ATOMIZE_GROUNDING_AGENT_CONTRACT_VERSION",
    "ATOMIZE_GROUNDING_AGENT_TOOL_NAME",
    "AtomizeGroundingAgentAdapter",
    "AtomizeGroundingAgentKind",
    "atomize_grounding_agent_tool_schema",
]
