"""Whole-catalog semantic selection for natural-language Help lookup."""

from __future__ import annotations

import json

import pytest

from memcommit.help_application import describe_operation
from memcommit.help_lookup_application import (
    HELP_LOOKUP_EXECUTION_POLICY,
    HELP_LOOKUP_REQUEST_LIMIT,
    HelpLookupError,
    execute_help_lookup,
    prepare_help_lookup,
)
from memcommit.semantic_execution import ExecutionStrategy


class _Provider:
    def __init__(self, raw: object) -> None:
        self.raw = raw
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls.append((prompt, operation, output_schema))
        return self.raw


def _operations():
    return tuple(
        describe_operation(name)
        for name in ("compare", "query", "search")
    )


def test_lookup_returns_exactly_three_catalog_records_in_model_order():
    plan = prepare_help_lookup(
        "Compare two Contexts and find relevant Memories.",
        operations=_operations(),
    )
    provider = _Provider(
        '{"operations":["compare","search","query"]}'
    )

    result = execute_help_lookup(plan, provider)

    assert [operation.name for operation in result] == [
        "compare",
        "search",
        "query",
    ]
    assert provider.calls[0][1] == "help"
    assert provider.calls[0][2] == plan.output_schema
    assert plan.output_schema["properties"]["operations"]["minItems"] == 3
    assert plan.output_schema["properties"]["operations"]["maxItems"] == 3


def test_lookup_weak_request_still_returns_three_ranked_candidates():
    plan = prepare_help_lookup("🦆 ??? 123", operations=_operations())
    provider = _Provider(
        '{"operations":["query","search","compare"]}'
    )

    assert [
        operation.name for operation in execute_help_lookup(plan, provider)
    ] == ["query", "search", "compare"]
    payload = json.loads(plan.prompt.partition("HELP LOOKUP PAYLOAD:\n")[2])
    assert payload["request"] == "🦆 ??? 123"
    assert payload["result_count"] == 3
    assert set(payload["operations"][0]) >= {
        "name",
        "summary",
        "best_for",
        "flow",
        "execution",
        "effect",
    }


def test_lookup_prompt_allows_short_outcome_language_without_catalog_terms():
    plan = prepare_help_lookup(
        "답 해결할 수 있는 문장",
        operations=_operations(),
    )

    assert "short, colloquial, metaphorical, or fragmentary language" in plan.prompt
    assert "Do not require it to repeat MemCommit nouns or catalog wording" in plan.prompt
    assert "answer-producing sentence or response may directly match query" in plan.prompt


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        '{"operations":["missing"]}',
        '{"operations":["compare","compare"]}',
        '{"operations":[]}',
        '{"operations":["compare"]}',
        '{"operations":["compare","query"]}',
        '{"operations":["compare","query","search","compare"]}',
        '{"operations":["compare"],"why":"because"}',
        '{"operations":"compare"}',
        '{"operations":[1]}',
        '{"operations":[],"operations":[]}',
    ],
)
def test_lookup_rejects_malformed_unknown_duplicate_or_explanatory_output(raw):
    plan = prepare_help_lookup("request", operations=_operations())

    with pytest.raises(HelpLookupError, match="invalid|unknown"):
        execute_help_lookup(plan, _Provider(raw))


@pytest.mark.parametrize(
    "lookup_text",
    ["", "   ", "x" * (HELP_LOOKUP_REQUEST_LIMIT + 1)],
)
def test_lookup_rejects_invalid_input_before_provider_execution(lookup_text):
    with pytest.raises(HelpLookupError):
        prepare_help_lookup(lookup_text, operations=_operations())


def test_lookup_rejects_catalog_too_small_for_three_distinct_candidates():
    with pytest.raises(HelpLookupError, match="at least 3"):
        prepare_help_lookup("request", operations=_operations()[:2])


def test_lookup_declares_bounded_top_k_semantics_without_hidden_staging():
    assert HELP_LOOKUP_EXECUTION_POLICY.operation == "help"
    assert (
        HELP_LOOKUP_EXECUTION_POLICY.strategy
        is ExecutionStrategy.TOP_K_RERANK
    )
    assert HELP_LOOKUP_EXECUTION_POLICY.staged_supported is False
