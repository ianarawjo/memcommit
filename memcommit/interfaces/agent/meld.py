"""Versioned JSON-safe agent adapter for the public Meld facade."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from memcommit.api import (
    MeldApplyResult,
    MeldAuthorityError,
    MeldConflictError,
    MeldContextError,
    MeldError,
    MeldExecutionError,
    MeldInputError,
    MeldProviderFailure,
    MeldSessionResult,
    MeldStorageError,
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


MELD_AGENT_CONTRACT_VERSION = 1
MELD_AGENT_TOOL_NAME = "memcommit_meld"
MeldAgentKind = Literal["start", "open", "comment", "preserve", "defer", "apply"]


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
    if kind not in {"start", "open", "comment", "preserve", "defer", "apply"}:
        raise AgentRequestError(
            "kind must be one of: start, open, comment, preserve, defer, apply."
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
    if kind == "comment":
        exact_fields(
            value,
            required={"version", "kind", "target_context", "comment"},
            optional=frozenset({"issue_uid", "revision", "revises_turn_uids"}),
            label="Meld comment request",
        )
        raw_revises = value.get("revises_turn_uids", [])
        if not isinstance(raw_revises, list):
            raise AgentRequestError("revises_turn_uids must be a list.")
        return kind, {
            "target_context": text_value(
                value["target_context"],
                field="target_context",
            ),
            "comment": text_value(value["comment"], field="comment"),
            "issue_uid": text_value(
                value.get("issue_uid"),
                field="issue_uid",
                optional=True,
            ),
            "revision": text_value(
                value.get("revision", "EXTEND"),
                field="revision",
            ),
            "revises_turn_uids": tuple(
                text_value(item, field="revises_turn_uids item")
                for item in raw_revises
            ),
        }
    exact_fields(
        value,
        required={"version", "kind", "target_context"},
        label=f"Meld {kind} request",
    )
    return kind, {
        "target_context": text_value(
            value["target_context"],
            field="target_context",
        )
    }


def _session_result(result: MeldSessionResult) -> JsonObject:
    return {
        "session_uid": result.session_uid,
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
            "open",
            "comment",
            "preserve",
            "defer",
            "apply",
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
        apply_result = result if isinstance(result, MeldApplyResult) else None
        session = apply_result.session if apply_result is not None else result
        return {
            "version": MELD_AGENT_CONTRACT_VERSION,
            "ok": True,
            "kind": kind,
            "result": {
                "session": _session_result(session),
                **(
                    {
                        "recovered": apply_result.recovered,
                        "checkpoint_uid": apply_result.checkpoint_uid,
                        "result_count": apply_result.result_count,
                    }
                    if apply_result is not None
                    else {}
                ),
            },
        }


def meld_agent_tool_schema() -> JsonObject:
    """Return one strict union schema for versioned Meld actions."""

    text = {"type": "string", "minLength": 1, "pattern": r".*\S.*"}
    kinds = ["start", "open", "comment", "preserve", "defer", "apply"]
    return {
        "name": MELD_AGENT_TOOL_NAME,
        "description": (
            "Start or continue a reviewed MemCommit Meld through stable "
            "application operations; Apply never calls the provider."
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
                "mode": {"type": "string", "enum": ["directional", "symmetric"]},
                "create_target": {"type": "boolean"},
                "left_descendants": {"type": "boolean"},
                "right_descendants": {"type": "boolean"},
                "comment": text,
                "issue_uid": {"type": ["string", "null"], "minLength": 1},
                "revision": {
                    "type": "string",
                    "enum": ["CONFIRM", "EXTEND", "CORRECT", "RETRACT"],
                },
                "revises_turn_uids": {"type": "array", "items": text},
            },
        },
    }


__all__ = [
    "MELD_AGENT_CONTRACT_VERSION",
    "MELD_AGENT_TOOL_NAME",
    "MeldAgentAdapter",
    "MeldAgentKind",
    "meld_agent_tool_schema",
]
