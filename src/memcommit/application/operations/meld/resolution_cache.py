"""Exact profile-local semantic outcomes for complete Meld reconciliations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from memcommit.infrastructure.config import Config
from memcommit.application.operations.meld.model import MELD_TEXT_LIMIT, MeldSession
from memcommit.application.operations.meld.provider import MELD_RESPONSE_CHAR_LIMIT
from memcommit.infrastructure.providers.types import (
    CODEX_CHATGPT_PROVIDER,
    ProviderIdentity,
)


MELD_RESOLUTION_BRANCH_KIND = "MELD_RESOLUTION_BRANCH"
MELD_RESOLUTION_BRANCH_SCHEMA_VERSION = 1
# ISSUE_RESOLUTION remains readable for compatibility with branches written
# before local choices became provider-free drafts. New command paths publish
# only complete ALL/REMAINING outcomes.
_BRANCH_KINDS = {"WHOLE_SET_STRATEGY", "ISSUE_RESOLUTION"}
_SCOPES = {"ALL", "ISSUE", "REMAINING"}
_HEX = frozenset("0123456789abcdef")


class MeldResolutionCacheError(ValueError):
    """A saved Meld resolution branch is malformed or unsafe."""


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in _HEX for character in value)
    )


def configured_meld_cache_identity() -> dict[str, object]:
    """Return the provider choice knowable before any provider connection."""
    config = Config()
    provider = config.semantic_provider()
    model = config.model_for_provider(provider)
    if provider == CODEX_CHATGPT_PROVIDER and model is None:
        model = "current-recommended"
    reasoning = (
        config.codex_reasoning_effort()
        if provider == CODEX_CHATGPT_PROVIDER
        else None
    )
    return {
        "provider": provider,
        "model": model,
        "reasoning_effort": reasoning,
    }


def _validate_configured_identity(value: object) -> dict[str, object]:
    expected = {"provider", "model", "reasoning_effort"}
    if not isinstance(value, dict) or set(value) != expected:
        raise MeldResolutionCacheError("Meld cache provider identity is invalid.")
    provider = value.get("provider")
    model = value.get("model")
    reasoning = value.get("reasoning_effort")
    if (
        not isinstance(provider, str)
        or not provider
        or (model is not None and (not isinstance(model, str) or not model))
        or (
            reasoning is not None
            and (not isinstance(reasoning, str) or not reasoning)
        )
    ):
        raise MeldResolutionCacheError("Meld cache provider identity is invalid.")
    return {
        "provider": provider,
        "model": model,
        "reasoning_effort": reasoning,
    }


def _origin_provider_record(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    if isinstance(value, ProviderIdentity):
        value = {
            "provider": value.provider,
            "model": value.model,
            "model_digest": value.model_digest,
            "runtime": value.runtime,
            "endpoint": value.endpoint,
            "reasoning_effort": value.reasoning_effort,
        }
    expected = {
        "provider",
        "model",
        "model_digest",
        "runtime",
        "endpoint",
        "reasoning_effort",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise MeldResolutionCacheError("Meld cache origin provider is invalid.")
    for key in expected:
        item = value.get(key)
        if item is not None and (not isinstance(item, str) or not item):
            raise MeldResolutionCacheError("Meld cache origin provider is invalid.")
    if not isinstance(value.get("provider"), str) or not isinstance(
        value.get("model"), str
    ):
        raise MeldResolutionCacheError("Meld cache origin provider is invalid.")
    return {key: value.get(key) for key in sorted(expected)}


def meld_resolution_cache_key(
    request_digest: str,
    configured_provider: dict[str, object],
) -> str:
    """Bind one branch to the exact semantic request and provider choice."""
    if not _is_digest(request_digest):
        raise MeldResolutionCacheError("Meld request digest is invalid.")
    provider = _validate_configured_identity(configured_provider)
    material = {
        "schema_version": MELD_RESOLUTION_BRANCH_SCHEMA_VERSION,
        "request_digest": request_digest,
        "configured_provider": provider,
    }
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return _digest(encoded)


@dataclass(frozen=True)
class MeldResolutionBranch:
    """One fully validated response for an exact pending resolution turn."""

    key: str
    request_digest: str
    configured_provider: dict[str, object]
    origin_provider: dict[str, object] | None
    branch_kind: str
    scope: str
    issue_count: int
    instruction: str
    completion: str

    @classmethod
    def create(
        cls,
        *,
        session: MeldSession,
        request_digest: str,
        configured_provider: dict[str, object],
        origin_provider: ProviderIdentity | None,
        completion: str,
    ) -> "MeldResolutionBranch":
        current = session.current_turn
        if current is None or current.sequence <= 0:
            raise MeldResolutionCacheError(
                "Only a follow-up Meld resolution can be cached."
            )
        if current.scope not in _SCOPES:
            raise MeldResolutionCacheError("Meld resolution scope is invalid.")
        branch_kind = (
            "ISSUE_RESOLUTION"
            if current.scope == "ISSUE"
            else "WHOLE_SET_STRATEGY"
        )
        provider = _validate_configured_identity(configured_provider)
        key = meld_resolution_cache_key(request_digest, provider)
        record = cls(
            key=key,
            request_digest=request_digest,
            configured_provider=provider,
            origin_provider=_origin_provider_record(origin_provider),
            branch_kind=branch_kind,
            scope=current.scope,
            issue_count=len(current.issue_uids),
            instruction=current.comment,
            completion=completion,
        )
        return cls.from_dict(record.to_dict())

    @classmethod
    def from_dict(cls, value: object) -> "MeldResolutionBranch":
        expected = {
            "kind",
            "schema_version",
            "key",
            "request_digest",
            "configured_provider",
            "origin_provider",
            "branch_kind",
            "scope",
            "issue_count",
            "instruction",
            "instruction_sha256",
            "completion",
            "completion_sha256",
        }
        if not isinstance(value, dict) or set(value) != expected:
            raise MeldResolutionCacheError("Saved Meld resolution branch is invalid.")
        key = value.get("key")
        request_digest = value.get("request_digest")
        branch_kind = value.get("branch_kind")
        scope = value.get("scope")
        issue_count = value.get("issue_count")
        instruction = value.get("instruction")
        completion = value.get("completion")
        if (
            value.get("kind") != MELD_RESOLUTION_BRANCH_KIND
            or value.get("schema_version")
            != MELD_RESOLUTION_BRANCH_SCHEMA_VERSION
            or not _is_digest(key)
            or not _is_digest(request_digest)
            or branch_kind not in _BRANCH_KINDS
            or scope not in _SCOPES
            or (branch_kind == "ISSUE_RESOLUTION") != (scope == "ISSUE")
            or not isinstance(issue_count, int)
            or isinstance(issue_count, bool)
            or issue_count < 0
            or (scope != "ISSUE" and issue_count != 0)
            or (scope == "ISSUE" and issue_count == 0)
            or not isinstance(instruction, str)
            or not instruction.strip()
            or len(instruction) > MELD_TEXT_LIMIT
            or not isinstance(completion, str)
            or not completion.strip()
            or len(completion) > MELD_RESPONSE_CHAR_LIMIT
            or value.get("instruction_sha256") != _digest(instruction)
            or value.get("completion_sha256") != _digest(completion)
        ):
            raise MeldResolutionCacheError("Saved Meld resolution branch is invalid.")
        provider = _validate_configured_identity(value.get("configured_provider"))
        if key != meld_resolution_cache_key(request_digest, provider):
            raise MeldResolutionCacheError("Saved Meld resolution key is stale.")
        return cls(
            key=key,
            request_digest=request_digest,
            configured_provider=provider,
            origin_provider=_origin_provider_record(value.get("origin_provider")),
            branch_kind=branch_kind,
            scope=scope,
            issue_count=issue_count,
            instruction=instruction,
            completion=completion,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": MELD_RESOLUTION_BRANCH_KIND,
            "schema_version": MELD_RESOLUTION_BRANCH_SCHEMA_VERSION,
            "key": self.key,
            "request_digest": self.request_digest,
            "configured_provider": self.configured_provider,
            "origin_provider": self.origin_provider,
            "branch_kind": self.branch_kind,
            "scope": self.scope,
            "issue_count": self.issue_count,
            "instruction": self.instruction,
            "instruction_sha256": _digest(self.instruction),
            "completion": self.completion,
            "completion_sha256": _digest(self.completion),
        }
