"""Shared versioned JSON-envelope mechanics for agent adapters."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, overload


AGENT_ERROR_MESSAGE_LIMIT = 1_000
JsonObject = dict[str, Any]


class AgentRequestError(ValueError):
    """Machine input was invalid before an operation call."""


def object_value(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise AgentRequestError(f"{label} must be an object with text keys.")
    return value


def exact_fields(
    value: Mapping[str, object],
    *,
    required: set[str],
    optional: frozenset[str] = frozenset(),
    label: str,
) -> None:
    keys = set(value)
    missing = sorted(required - keys)
    unknown = sorted(keys - required - optional)
    if missing:
        raise AgentRequestError(
            f"{label} is missing required fields: {', '.join(missing)}."
        )
    if unknown:
        raise AgentRequestError(
            f"{label} contains unknown fields: {', '.join(unknown)}."
        )


@overload
def text_value(
    value: object,
    *,
    field: str,
    optional: Literal[False] = False,
) -> str: ...


@overload
def text_value(
    value: object,
    *,
    field: str,
    optional: Literal[True],
) -> str | None: ...


def text_value(value: object, *, field: str, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise AgentRequestError(f"{field} must be nonblank text.")
    return value


def error_response(
    *,
    version: int,
    kind: str | None,
    code: str,
    message: str,
    retryable: bool,
) -> JsonObject:
    """Build one bounded, control-safe failure envelope."""

    bounded_message = "".join(
        character if ord(character) >= 32 and ord(character) != 127 else " "
        for character in message
    ).strip()
    if len(bounded_message) > AGENT_ERROR_MESSAGE_LIMIT:
        bounded_message = (
            bounded_message[: AGENT_ERROR_MESSAGE_LIMIT - 1].rstrip() + "…"
        )
    return {
        "version": version,
        "ok": False,
        "kind": kind,
        "error": {
            "code": code,
            "message": bounded_message,
            "retryable": retryable,
        },
    }


__all__ = [
    "AGENT_ERROR_MESSAGE_LIMIT",
    "AgentRequestError",
    "JsonObject",
    "error_response",
    "exact_fields",
    "object_value",
    "text_value",
]
