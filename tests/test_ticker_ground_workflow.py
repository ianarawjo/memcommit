from __future__ import annotations

import json

import pytest

from memcommit.eval.ticker_ground_workflow import (
    TICKER_WORKFLOW_GOAL,
    TICKER_WORKFLOW_STAGE_SIZES,
    TickerWorkflowError,
    load_ticker_workflow,
)


def test_ticker_workflow_freezes_vague_goal_and_monotonic_stages() -> None:
    corpus = load_ticker_workflow()

    assert corpus.vague_goal == "티커가 어떻게 만들어지는지 규칙을 알고 싶어"
    assert corpus.vague_goal == TICKER_WORKFLOW_GOAL
    assert corpus.stage_sizes == TICKER_WORKFLOW_STAGE_SIZES
    assert len(corpus.examples) == 50
    prior_ids: set[str] = set()
    for reveal_round, expected_size in enumerate(corpus.stage_sizes, 1):
        examples = corpus.examples_through_round(reveal_round)
        ids = {example.case_id for example in examples}
        assert len(examples) == expected_size
        assert prior_ids < ids
        prior_ids = ids


def test_ticker_workflow_separates_mappings_from_explicit_unknowns() -> None:
    corpus = load_ticker_workflow()
    determined = tuple(
        example for example in corpus.examples if example.resolution == "DETERMINED"
    )
    unresolved = tuple(
        example for example in corpus.examples if example.resolution == "UNRESOLVED"
    )

    assert len(determined) == 46
    assert len(unresolved) == 4
    assert all(example.expected_output for example in determined)
    assert all(not example.expected_output for example in unresolved)
    assert all("remains unresolved" in example.proposition for example in unresolved)
    assert {example.reveal_round for example in unresolved} == {5}


def test_ticker_workflow_has_required_boundary_coverage() -> None:
    corpus = load_ticker_workflow()
    observed = {
        category for example in corpus.examples for category in example.categories
    }

    assert observed == set(corpus.coverage_categories)
    assert {example.role for example in corpus.examples} == {
        "FIT",
        "BOUNDARY",
        "CONTRAST",
    }
    assert "collision" in observed
    assert "unsupported_transliteration" in observed
    assert "unsupported_separator" in observed
    assert "unsupported_security_descriptor" in observed


def test_ticker_workflow_rejects_a_hidden_mapping_rewrite(tmp_path) -> None:
    corpus = load_ticker_workflow()
    value = json.loads(corpus.path.read_text(encoding="utf-8"))
    value["examples"][0]["expected_output"] = "WRONG"
    path = tmp_path / "ticker.json"
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(
        TickerWorkflowError,
        match="must use its exact mapping",
    ):
        load_ticker_workflow(path)


def test_ticker_workflow_rejects_silently_resolving_an_unknown(tmp_path) -> None:
    corpus = load_ticker_workflow()
    value = json.loads(corpus.path.read_text(encoding="utf-8"))
    value["examples"][45]["expected_output"] = "EG"
    path = tmp_path / "ticker.json"
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(
        TickerWorkflowError,
        match="must stay visibly unresolved",
    ):
        load_ticker_workflow(path)
