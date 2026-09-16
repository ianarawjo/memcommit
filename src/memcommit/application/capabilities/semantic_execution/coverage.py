"""Application-owned exact input coverage for staged semantic execution."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Mapping


class CoverageError(RuntimeError):
    """A staged execution omitted, duplicated, or invented an input identity."""


@dataclass
class InputCoverageLedger:
    """Record which frozen inputs completed exactly one provider batch."""

    expected_ids: tuple[str, ...]
    _seen: set[str] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self) -> None:
        if any(not isinstance(value, str) or not value for value in self.expected_ids):
            raise CoverageError("Semantic coverage ids must be nonempty text.")
        if len(self.expected_ids) != len(set(self.expected_ids)):
            raise CoverageError("Semantic coverage ids must be unique.")

    def record(self, values: tuple[str, ...]) -> None:
        if len(values) != len(set(values)):
            raise CoverageError("One semantic batch repeated an input id.")
        expected = set(self.expected_ids)
        unknown = set(values) - expected
        repeated = set(values) & self._seen
        if unknown:
            raise CoverageError("One semantic batch reported an unknown input id.")
        if repeated:
            raise CoverageError("Staged semantic execution repeated an input id.")
        self._seen.update(values)

    def finalize(self) -> None:
        if self._seen != set(self.expected_ids):
            raise CoverageError("Staged semantic execution did not cover every input.")


def exact_source_assignment_schema(
    expected_ids: tuple[str, ...],
    *,
    relation_key_schema: Mapping[str, object],
) -> dict[str, object]:
    """Describe one source-to-relation assignment for every frozen input.

    Codex structured output does not support ``uniqueItems``. Exact cardinality
    plus a frozen alias enum makes omissions harder during generation, while
    :func:`decode_exact_source_assignments` remains the authority for global
    uniqueness and complete coverage.
    """

    InputCoverageLedger(expected_ids)
    return {
        "type": "array",
        "minItems": len(expected_ids),
        "maxItems": len(expected_ids),
        "items": {
            "type": "object",
            "properties": {
                "source_memory_id": {
                    "type": "string",
                    "enum": list(expected_ids),
                },
                "relation_key": deepcopy(dict(relation_key_schema)),
            },
            "required": ["source_memory_id", "relation_key"],
            "additionalProperties": False,
        },
    }


def decode_exact_source_assignments(
    value: object,
    expected_ids: tuple[str, ...],
) -> tuple[tuple[str, str], ...]:
    """Decode an exact source-indexed relation assignment ledger."""

    ledger = InputCoverageLedger(expected_ids)
    if not isinstance(value, list) or len(value) != len(expected_ids):
        raise CoverageError(
            "Semantic source assignments must contain one row per input."
        )
    assignments: list[tuple[str, str]] = []
    for record in value:
        if (
            not isinstance(record, dict)
            or set(record) != {"source_memory_id", "relation_key"}
        ):
            raise CoverageError("Invalid semantic source assignment.")
        source_id = record["source_memory_id"]
        relation_key = record["relation_key"]
        if (
            not isinstance(source_id, str)
            or not isinstance(relation_key, str)
            or not relation_key
        ):
            raise CoverageError("Invalid semantic source assignment.")
        ledger.record((source_id,))
        assignments.append((source_id, relation_key))
    ledger.finalize()
    return tuple(assignments)
