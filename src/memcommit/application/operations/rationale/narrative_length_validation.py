"""Exact public narrative-length validation shared by Rationale skills."""

from __future__ import annotations

from memcommit.application.operations.rationale.model import (
    MAX_RATIONALE_PROVENANCE_LIMIT,
    RationaleLimitUnit,
    RationaleRulesError,
)


def measure_rationale_text(value: str, unit: RationaleLimitUnit) -> int:
    """Measure one NFC narrative in the exact public CLI unit."""

    if unit is RationaleLimitUnit.CHARACTERS:
        return len(value)
    if unit is RationaleLimitUnit.BYTES:
        return len(value.encode("utf-8"))
    return len(value.split())


def validate_rationale_limit(
    limit: int,
    unit: RationaleLimitUnit | str | None = None,
) -> RationaleLimitUnit:
    """Validate a positive receipt bound before store or provider access."""

    if type(limit) is not int or not 1 <= limit <= MAX_RATIONALE_PROVENANCE_LIMIT:
        raise RationaleRulesError(
            f"Rationale --limit must be between 1 and {MAX_RATIONALE_PROVENANCE_LIMIT}."
        )
    try:
        return (
            unit
            if isinstance(unit, RationaleLimitUnit)
            else RationaleLimitUnit(unit or RationaleLimitUnit.WORDS.value)
        )
    except ValueError as error:
        raise RationaleRulesError(
            "Rationale has an unsupported length unit."
        ) from error
