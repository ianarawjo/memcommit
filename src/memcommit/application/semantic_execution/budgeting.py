"""Deterministic request-size accounting for semantic execution."""

from __future__ import annotations

import json

from memcommit.application.semantic_execution.model import BudgetVector


def _json_chars(value: object) -> int:
    return len(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def json_budget(
    payload: object,
    *,
    item_count: int = 0,
    output_schema: object | None = None,
    expected_output_items: int = 0,
    relation_edges: int = 0,
) -> BudgetVector:
    """Measure JSON payload and schema separately without guessing tokenization."""

    return BudgetVector(
        input_chars=_json_chars(payload),
        item_count=item_count,
        schema_chars=(0 if output_schema is None else _json_chars(output_schema)),
        expected_output_items=expected_output_items,
        relation_edges=relation_edges,
    )
