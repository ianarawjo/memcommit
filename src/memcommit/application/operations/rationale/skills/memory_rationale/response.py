"""Bounded provenance response contract shared by Memory and Context Rationale."""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, replace

from memcommit.application.operations.rationale.narrative_length_validation import (
    measure_rationale_text,
)
from memcommit.application.operations.rationale.model import (
    RationaleLimitUnit,
    RationaleNarrativeStatus,
    RationaleSynthesisError,
)
from memcommit.application.operations.rationale.skills.memory_rationale.rules import (
    RATIONALE_RULESET_VERSION,
)

RATIONALE_RESPONSE_CHAR_LIMIT = 100_000


class _RationaleLimitExceeded(RationaleSynthesisError):
    """A valid structured draft exceeded the requested presentation bound."""

    def __init__(
        self,
        *,
        text: str,
        length: int,
        limit: int,
        unit: RationaleLimitUnit,
    ) -> None:
        self.text = text
        self.length = length
        self.limit = limit
        self.unit = unit
        super().__init__(
            "The Rationale provider exceeded the requested complete-narrative "
            f"limit of {limit} {unit.value}."
        )


@dataclass(frozen=True)
class RationaleNarrativeProjection:
    """One complete bounded receipt over the frozen retained Trace."""

    status: RationaleNarrativeStatus
    text: str
    limit: int
    unit: RationaleLimitUnit
    length: int
    ruleset_version: str = RATIONALE_RULESET_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "text": self.text,
            "limit": self.limit,
            "unit": self.unit.value,
            "length": self.length,
            "ruleset_version": self.ruleset_version,
        }


def _strict_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise RationaleSynthesisError(f"Duplicate Rationale provider field: {key}.")
        result[key] = value
    return result


def _output_schema(
    *,
    limit: int,
    unit: RationaleLimitUnit,
) -> dict[str, object]:
    provenance_schema: dict[str, object] = {
        "type": "string",
        "minLength": 1,
        "maxLength": (
            limit
            if unit is RationaleLimitUnit.CHARACTERS
            else RATIONALE_RESPONSE_CHAR_LIMIT
        ),
    }
    return {
        "type": "object",
        "properties": {"provenance": provenance_schema},
        "required": ["provenance"],
        "additionalProperties": False,
    }


def _parse_projection(
    raw: object,
    *,
    limit: int,
    unit: RationaleLimitUnit,
) -> RationaleNarrativeProjection:
    if (
        not isinstance(raw, str)
        or not raw.strip()
        or len(raw) > RATIONALE_RESPONSE_CHAR_LIMIT
    ):
        raise RationaleSynthesisError(
            "The Rationale provider returned invalid structured output."
        )
    try:
        value = json.loads(raw, object_pairs_hook=_strict_json_object)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise RationaleSynthesisError(
            "The Rationale provider returned invalid structured output."
        ) from error
    if not isinstance(value, dict) or set(value) != {"provenance"}:
        raise RationaleSynthesisError(
            "The Rationale provider returned an invalid object."
        )
    raw_text = value["provenance"]
    if not isinstance(raw_text, str):
        raise RationaleSynthesisError(
            "The Rationale provider returned invalid provenance text."
        )
    text = unicodedata.normalize("NFC", raw_text.strip())
    non_narrative_sentinels = {"/", "null", ":null", "undefined"}
    if (
        not text
        or text.casefold() in non_narrative_sentinels
        or not any(character.isalnum() for character in text)
        or "\n" in raw_text
        or "\r" in raw_text
        or "→" in text
        or text.upper().startswith("PROVENANCE")
        or any(unicodedata.category(character) == "Cc" for character in text)
    ):
        raise RationaleSynthesisError(
            "The Rationale provider returned a non-narrative provenance receipt."
        )
    length = measure_rationale_text(text, unit)
    if length > limit:
        raise _RationaleLimitExceeded(
            text=text,
            length=length,
            limit=limit,
            unit=unit,
        )
    return RationaleNarrativeProjection(
        status=RationaleNarrativeStatus.AVAILABLE,
        text=text,
        limit=limit,
        unit=unit,
        length=length,
    )


def rationale_output_schema(
    *,
    limit: int,
    unit: RationaleLimitUnit,
) -> dict[str, object]:
    """Expose the shared structured-output contract to typed rationale subjects."""

    return _output_schema(limit=limit, unit=unit)


def parse_rationale_projection(
    raw: object,
    *,
    limit: int,
    unit: RationaleLimitUnit,
    ruleset_version: str = RATIONALE_RULESET_VERSION,
) -> RationaleNarrativeProjection:
    """Validate one narrative while retaining the subject's ruleset identity."""

    return replace(
        _parse_projection(raw, limit=limit, unit=unit),
        ruleset_version=ruleset_version,
    )
