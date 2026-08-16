"""Versioned read-only agent adapter for Distill."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from memcommit.api import (
    DistillProposal,
    MemCommitClient,
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
from memcommit.interfaces.agent.ground_artifacts import GroundArtifactRegistry


DISTILL_AGENT_CONTRACT_VERSION = 1
DISTILL_AGENT_TOOL_NAME = "memcommit_distill"
DistillAgentKind = Literal["context", "ground"]


def _boolean(value: object, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise AgentRequestError(f"{field} must be a boolean.")
    return value


def _parse_request(payload: object) -> tuple[DistillAgentKind, dict[str, object]]:
    value = object_value(payload, label="Distill request")
    if value.get("version") != DISTILL_AGENT_CONTRACT_VERSION or isinstance(
        value.get("version"), bool
    ):
        raise AgentRequestError(
            f"version must be exactly {DISTILL_AGENT_CONTRACT_VERSION}."
        )
    kind = value.get("kind")
    if kind == "context":
        exact_fields(
            value,
            required={"version", "kind"},
            optional=frozenset(
                {"context_name", "goal", "include_descendants", "follow_embeds"}
            ),
            label="Context Distill request",
        )
        return kind, {
            "context_name": text_value(
                value.get("context_name"), field="context_name", optional=True
            ),
            "goal": text_value(value.get("goal"), field="goal", optional=True),
            "include_descendants": _boolean(
                value.get("include_descendants", False),
                field="include_descendants",
            ),
            "follow_embeds": _boolean(
                value.get("follow_embeds", False),
                field="follow_embeds",
            ),
        }
    if kind == "ground":
        exact_fields(
            value,
            required={"version", "kind", "ground_name"},
            label="Ground Distill request",
        )
        return kind, {
            "ground_name": text_value(value["ground_name"], field="ground_name")
        }
    raise AgentRequestError("kind must be one of: context, ground.")


def _serialize(result: DistillProposal) -> JsonObject:
    return {
        "analysis_uid": result.analysis_uid,
        "source_context": result.source_context,
        "source_digest": result.source_digest,
        "goal": result.goal,
        "overview": result.overview,
        "rules": [
            {
                "uid": rule.uid,
                "content": rule.content,
                "rationale": rule.rationale,
                "support_memory_uids": list(rule.support_memory_uids),
                "boundary_memory_uids": list(rule.boundary_memory_uids),
            }
            for rule in result.rules
        ],
        "outside_memory_uids": list(result.outside_memory_uids),
        "origin": result.origin,
        "effect": "NONE",
    }


_ERRORS: tuple[tuple[type[SemanticError], str, str, bool], ...] = (
    (SemanticInputError, "invalid_request", "The Distill request is invalid.", False),
    (SemanticContextError, "context_unavailable", "The Distill Source is unavailable.", False),
    (SemanticAuthorityError, "authority_denied", "Distill is not authorized for this Source.", False),
    (SemanticProviderFailure, "provider_failure", "The Distill provider failed.", True),
    (SemanticStorageError, "storage_failure", "Distill could not access local state.", False),
    (SemanticConflictError, "stale_state", "The Distill input changed.", False),
    (SemanticExecutionError, "execution_failed", "Distill failed before publishing a proposal.", False),
)


class DistillAgentAdapter:
    def __init__(
        self,
        client: MemCommitClient,
        *,
        artifacts: GroundArtifactRegistry | None = None,
    ) -> None:
        if not isinstance(client, MemCommitClient):
            raise TypeError("DistillAgentAdapter requires a MemCommitClient.")
        self._client = client
        self._artifacts = artifacts

    def invoke(self, payload: object) -> JsonObject:
        kind: DistillAgentKind | None = None
        if isinstance(payload, Mapping) and payload.get("kind") in {"context", "ground"}:
            kind = payload["kind"]  # type: ignore[assignment]
        try:
            kind, arguments = _parse_request(payload)
        except AgentRequestError as error:
            return error_response(
                version=DISTILL_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="invalid_request",
                message=str(error),
                retryable=False,
            )
        try:
            result = (
                self._client.distill_context(**arguments)  # type: ignore[arg-type]
                if kind == "context"
                else self._client.distill_ground(**arguments)  # type: ignore[arg-type]
            )
        except SemanticError as error:
            for error_type, code, message, retryable in _ERRORS:
                if isinstance(error, error_type):
                    return error_response(
                        version=DISTILL_AGENT_CONTRACT_VERSION,
                        kind=kind,
                        code=code,
                        message=(str(error) if error_type in {SemanticInputError, SemanticContextError, SemanticAuthorityError} else message),
                        retryable=retryable,
                    )
            return error_response(
                version=DISTILL_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="distill_failed",
                message="Distill failed without a more specific public category.",
                retryable=False,
            )
        except Exception:
            return error_response(
                version=DISTILL_AGENT_CONTRACT_VERSION,
                kind=kind,
                code="internal_error",
                message="The Distill tool failed internally.",
                retryable=False,
            )
        if kind == "ground" and self._artifacts is not None:
            self._artifacts.retain_artifact(result)
        return {
            "version": DISTILL_AGENT_CONTRACT_VERSION,
            "ok": True,
            "kind": kind,
            "result": _serialize(result),
        }


def distill_agent_tool_schema() -> JsonObject:
    text = {"type": "string", "minLength": 1, "pattern": r".*\S.*"}
    version = {"type": "integer", "const": DISTILL_AGENT_CONTRACT_VERSION}
    return {
        "name": DISTILL_AGENT_TOOL_NAME,
        "description": (
            "Propose evidence-bound Rules from one Context or bound Ground; "
            "the Source and Ground remain unchanged."
        ),
        "parameters": {
            "type": "object",
            "oneOf": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["version", "kind"],
                    "properties": {
                        "version": version,
                        "kind": {"type": "string", "const": "context"},
                        "context_name": {**text, "type": ["string", "null"]},
                        "goal": {**text, "type": ["string", "null"]},
                        "include_descendants": {"type": "boolean", "default": False},
                        "follow_embeds": {"type": "boolean", "default": False},
                    },
                },
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["version", "kind", "ground_name"],
                    "properties": {
                        "version": version,
                        "kind": {"type": "string", "const": "ground"},
                        "ground_name": text,
                    },
                },
            ],
        },
    }


__all__ = [
    "DISTILL_AGENT_CONTRACT_VERSION",
    "DISTILL_AGENT_TOOL_NAME",
    "DistillAgentAdapter",
    "distill_agent_tool_schema",
]
