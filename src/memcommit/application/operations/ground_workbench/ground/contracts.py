"""Operation-neutral validation shared by physical Ground workflows."""

from __future__ import annotations

import hashlib
import json
import re

from memcommit.core.context import Context


GROUND_TEXT_LIMIT = 20_000
GROUND_GOAL_WORD_LIMIT = 40

_GROUND_NAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}\Z")
_WINDOWS_RESERVED_NAMES = {
    "aux",
    "con",
    "nul",
    "prn",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}


class GroundError(ValueError):
    """Invalid or unsupported Ground input."""


def validate_ground_contract_name(value: object) -> str:
    """Return one portable Ground ID that is safe as a local filename."""

    if (
        not isinstance(value, str)
        or _GROUND_NAME.fullmatch(value) is None
        or value.endswith(".")
        or value.split(".", 1)[0] in _WINDOWS_RESERVED_NAMES
    ):
        raise GroundError(
            "Ground names must match "
            "[a-z0-9][a-z0-9._-]{0,127} and must not use a reserved "
            "Windows device name."
        )
    return value


def validate_ground_goal(
    value: object,
    *,
    empty: bool = False,
    label: str = "grounding goal",
) -> str:
    """Validate one newly authored, compact Ground goal."""

    if (
        not isinstance(value, str)
        or (not empty and not value.strip())
        or len(value) > GROUND_TEXT_LIMIT
    ):
        raise GroundError(f"Invalid {label}.")
    if len(value.split()) > GROUND_GOAL_WORD_LIMIT:
        raise GroundError(
            f"{label.capitalize()} must be {GROUND_GOAL_WORD_LIMIT} words or fewer."
        )
    return value


def context_frame_digest(ctx: Context) -> str:
    """Fingerprint one complete ordered direct Context record."""

    encoded = json.dumps(
        ctx.to_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
