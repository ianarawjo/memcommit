"""Versioned process-local agent adapter for reviewed Forget."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
from typing import Literal

from memcommit.adapters.python_api import (
    ForgetApplyResult,
    ForgetAuthorityError,
    ForgetConflictError,
    ForgetContextError,
    ForgetError,
    ForgetExecutionError,
    ForgetInputError,
    ForgetProviderFailure,
    ForgetReviewResult,
    ForgetStorageError,
    MemCommitClient,
)
from memcommit.adapters.interfaces.agent.contract import (
    AgentRequestError,
    JsonObject,
    error_response,
    exact_fields,
    object_value,
    text_value,
)


FORGET_AGENT_CONTRACT_VERSION = 1
FORGET_AGENT_TOOL_NAME = "memcommit_forget"
FORGET_AGENT_REVIEW_LIMIT = 64
ForgetAgentKind = Literal["analyze", "select", "revise", "apply"]


def _parse_request(payload: object) -> tuple[ForgetAgentKind, dict[str, object]]:
    value = object_value(payload, label="Forget request")
    version = value.get("version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != FORGET_AGENT_CONTRACT_VERSION
    ):
        raise AgentRequestError(
            f"version must be exactly {FORGET_AGENT_CONTRACT_VERSION}."
        )
    kind = value.get("kind")
    if kind not in {"analyze", "select", "revise", "apply"}:
        raise AgentRequestError(
            "kind must be one of: analyze, select, revise, apply."
        )
    if kind == "analyze":
        exact_fields(
            value,
            required={"version", "kind", "instruction"},
            optional=frozenset({"context_name"}),
            label="Forget analyze request",
        )
        return kind, {
            "instruction": text_value(value["instruction"], field="instruction"),
            "context_name": text_value(
                value.get("context_name"),
                field="context_name",
                optional=True,
            ),
        }

    required = {"version", "kind", "review_uid", "expected_version"}
    optional: frozenset[str] = frozenset()
    if kind == "select":
        required.update({"candidate_uid", "selection"})
        optional = frozenset({"custom_content"})
    elif kind == "revise":
        required.add("guidance")
    exact_fields(
        value,
        required=required,
        optional=optional,
        label=f"Forget {kind} request",
    )
    arguments: dict[str, object] = {
        "review_uid": text_value(value["review_uid"], field="review_uid"),
        "expected_version": text_value(
            value["expected_version"],
            field="expected_version",
        ),
    }
    if kind == "select":
        selection = value["selection"]
        if selection not in {"RECOMMENDED", "KEEP", "DELETE", "CUSTOM"}:
            raise AgentRequestError(
                "selection must be RECOMMENDED, KEEP, DELETE, or CUSTOM."
            )
        custom_content = value.get("custom_content", "")
        if not isinstance(custom_content, str):
            raise AgentRequestError("custom_content must be text.")
        if selection == "CUSTOM" and not custom_content.strip():
            raise AgentRequestError(
                "custom_content must be nonblank when selection is CUSTOM."
            )
        arguments.update(
            {
                "candidate_uid": text_value(
                    value["candidate_uid"], field="candidate_uid"
                ),
                "selection": selection,
                "custom_content": custom_content,
            }
        )
    elif kind == "revise":
        arguments["guidance"] = text_value(value["guidance"], field="guidance")
    return kind, arguments


def _review_result(review: ForgetReviewResult) -> JsonObject:
    return {
        "review_uid": review.review_uid,
        "version": review.version,
        "retention": review.retention,
        "source": {
            "context": review.source_context,
            "context_uid": review.source_context_uid,
        },
        "instruction": review.instruction,
        "overview": review.overview,
        "provider_used": review.provider_used,
        "candidates": [
            {
                "uid": candidate.uid,
                "source_memory_uid": candidate.source_memory_uid,
                "source_content": candidate.source_content,
                "recommendation": candidate.recommendation,
                "proposed_content": candidate.proposed_content,
                "rationale": candidate.rationale,
                "selection": candidate.selection,
                "selected_action": candidate.selected_action,
                "selected_content": candidate.selected_content,
            }
            for candidate in review.candidates
        ],
        "effect": "NONE",
    }


def _apply_result(
    result: ForgetApplyResult,
    *,
    recovered: bool,
) -> JsonObject:
    effect = "SOURCE_CHECKPOINT" if result.applied and not recovered else "NONE"
    return {
        "review_uid": result.review_uid,
        "version": result.version,
        "source": {
            "context": result.source_context,
            "context_uid": result.source_context_uid,
            "granted": result.granted,
        },
        "removed_count": result.removed_count,
        "edited_count": result.edited_count,
        "changed_count": result.changed_count,
        "checkpoint_uid": result.checkpoint_uid,
        "undo_available": result.undo_available,
        "applied": result.applied,
        "recovered": recovered,
        "effect": effect,
    }


_PUBLIC_ERRORS: tuple[tuple[type[ForgetError], str, str, bool], ...] = (
    (ForgetInputError, "invalid_request", "The Forget request is invalid.", False),
    (
        ForgetContextError,
        "context_unavailable",
        "The Forget Source Context is unavailable.",
        False,
    ),
    (ForgetAuthorityError, "authority_denied", "Forget authority was denied.", False),
    (ForgetProviderFailure, "provider_failure", "The Forget provider failed.", True),
    (ForgetConflictError, "stale_source", "The Forget Source changed.", False),
    (ForgetStorageError, "storage_failure", "Forget storage failed safely.", False),
    (ForgetExecutionError, "execution_failed", "Forget execution failed.", False),
)


class ForgetAgentAdapter:
    """Translate exact JSON actions to one process-local Forget lifecycle."""

    def __init__(
        self,
        client: MemCommitClient,
        *,
        review_limit: int = FORGET_AGENT_REVIEW_LIMIT,
    ) -> None:
        if not isinstance(client, MemCommitClient):
            raise TypeError("ForgetAgentAdapter requires a MemCommitClient.")
        if isinstance(review_limit, bool) or not isinstance(review_limit, int):
            raise TypeError("review_limit must be an integer.")
        if review_limit < 1:
            raise ValueError("review_limit must be positive.")
        self._client = client
        self._review_limit = review_limit
        self._reviews: OrderedDict[str, ForgetReviewResult] = OrderedDict()
        self._applied: dict[tuple[str, str], ForgetApplyResult] = {}

    def _remember(self, review: ForgetReviewResult) -> None:
        self._reviews[review.review_uid] = review
        self._reviews.move_to_end(review.review_uid)
        while len(self._reviews) > self._review_limit:
            forgotten_uid, _ = self._reviews.popitem(last=False)
            self._applied = {
                key: receipt
                for key, receipt in self._applied.items()
                if key[0] != forgotten_uid
            }

    def _error(
        self,
        *,
        kind: ForgetAgentKind | None,
        code: str,
        message: str,
        retryable: bool = False,
    ) -> JsonObject:
        return error_response(
            version=FORGET_AGENT_CONTRACT_VERSION,
            kind=kind,
            code=code,
            message=message,
            retryable=retryable,
        )

    def invoke(self, payload: object) -> JsonObject:
        kind: ForgetAgentKind | None = None
        if isinstance(payload, Mapping) and payload.get("kind") in {
            "analyze",
            "select",
            "revise",
            "apply",
        }:
            kind = payload["kind"]  # type: ignore[assignment]
        try:
            kind, arguments = _parse_request(payload)
        except AgentRequestError as error:
            return self._error(
                kind=kind,
                code="invalid_request",
                message=str(error),
            )

        try:
            if kind == "analyze":
                review = self._client.analyze_forget(**arguments)
                self._remember(review)
                result = _review_result(review)
            else:
                review_uid = arguments.pop("review_uid")
                expected_version = arguments.pop("expected_version")
                assert isinstance(review_uid, str)
                assert isinstance(expected_version, str)
                review = self._reviews.get(review_uid)
                if review is None:
                    return self._error(
                        kind=kind,
                        code="review_unavailable",
                        message=(
                            "The process-local Forget review is unavailable; "
                            "analyze it again in this tool process."
                        ),
                    )
                applied_key = (review_uid, expected_version)
                applied = self._applied.get(applied_key)
                if kind == "apply" and applied is not None:
                    result = _apply_result(applied, recovered=True)
                elif review.version != expected_version:
                    return self._error(
                        kind=kind,
                        code="stale_review",
                        message="The Forget review version is stale.",
                    )
                elif (review_uid, review.version) in self._applied:
                    return self._error(
                        kind=kind,
                        code="review_applied",
                        message="The Forget review version was already applied.",
                    )
                elif kind == "select":
                    review = self._client.select_forget(review, **arguments)
                    self._remember(review)
                    result = _review_result(review)
                elif kind == "revise":
                    review = self._client.revise_forget(review, **arguments)
                    self._remember(review)
                    result = _review_result(review)
                else:
                    applied = self._client.apply_forget(review)
                    self._applied[(review_uid, review.version)] = applied
                    result = _apply_result(applied, recovered=False)
        except ForgetError as error:
            for error_type, code, message, retryable in _PUBLIC_ERRORS:
                if isinstance(error, error_type):
                    return self._error(
                        kind=kind,
                        code=code,
                        message=(
                            str(error)
                            if isinstance(error, ForgetInputError)
                            else message
                        ),
                        retryable=retryable,
                    )
            return self._error(
                kind=kind,
                code="forget_failed",
                message="Forget failed without a more specific public category.",
            )
        except Exception:
            return self._error(
                kind=kind,
                code="internal_error",
                message="The Forget tool failed internally.",
            )
        return {
            "version": FORGET_AGENT_CONTRACT_VERSION,
            "ok": True,
            "kind": kind,
            "result": result,
        }


def forget_agent_tool_schema() -> JsonObject:
    text = {"type": "string", "minLength": 1, "pattern": r".*\S.*"}
    nullable_text = {**text, "type": ["string", "null"]}
    return {
        "name": FORGET_AGENT_TOOL_NAME,
        "description": (
            "Analyze, select, revise, or apply one reviewed Forget operation. "
            "The complete direct Source is reviewed as one frame. Review state "
            "is process-local and bounded; select, revise, and apply require the "
            "exact opaque version returned by the preceding action."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["version", "kind"],
            "properties": {
                "version": {
                    "type": "integer",
                    "const": FORGET_AGENT_CONTRACT_VERSION,
                },
                "kind": {
                    "type": "string",
                    "enum": ["analyze", "select", "revise", "apply"],
                },
                "instruction": text,
                "context_name": nullable_text,
                "review_uid": text,
                "expected_version": {
                    **text,
                    "description": (
                        "Opaque process-local version returned by analyze, "
                        "select, or revise."
                    ),
                },
                "candidate_uid": text,
                "selection": {
                    "type": "string",
                    "enum": ["RECOMMENDED", "KEEP", "DELETE", "CUSTOM"],
                },
                "custom_content": {"type": "string"},
                "guidance": text,
            },
        },
    }


__all__ = [
    "FORGET_AGENT_CONTRACT_VERSION",
    "FORGET_AGENT_REVIEW_LIMIT",
    "FORGET_AGENT_TOOL_NAME",
    "ForgetAgentAdapter",
    "ForgetAgentKind",
    "forget_agent_tool_schema",
]
