from __future__ import annotations

import json
from pathlib import Path

import pytest

from memcommit.eval.find_query_latency import (
    ALL_CASES,
    DEFAULT_CONDITIONS,
    FIND_CASES,
    QUERY_CASES,
    MatrixCondition,
    build_find_corpus,
    build_query_corpus,
    build_schedule,
    run_campaign,
    rescore_campaign,
    score_find,
    score_query,
)
from memcommit.provider_types import CompletionRun, ProviderIdentity
from memcommit.search import SearchMatch


def test_frozen_task3_corpora_have_reviewed_counts_and_locator_mapping():
    find_corpus = build_find_corpus()
    query_corpus = build_query_corpus()

    assert find_corpus.record_count == 300
    assert len(find_corpus.candidates) == 300
    assert set(find_corpus.locator_by_candidate_id.values()) >= {
        "local/personal-memory/2024-03/04",
        "local/personal-memory/2024-09/01",
        "local/personal-memory/2025-02/10",
    }
    assert query_corpus.record_count == 75
    assert "All content sent through" in query_corpus.source_content
    assert "healthcare Q&A agent cannot" in query_corpus.source_content


def test_schedule_contains_each_of_the_54_cells_once():
    schedule = build_schedule()

    assert len(schedule) == 54
    assert len({row["cell_id"] for row in schedule}) == 54
    assert {row["model"] for row in schedule} == {
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
    }
    assert {row["effort"] for row in schedule} == {"none", "low", "medium"}
    for case in ALL_CASES:
        assert sum(row["case_id"] == case.case_id for row in schedule) == 9


def test_find_score_uses_historical_results_without_calling_them_gold():
    corpus = build_find_corpus()
    case = FIND_CASES[0]
    candidate_by_locator = {
        locator: next(
            candidate
            for candidate in corpus.candidates
            if candidate.candidate_id == candidate_id
        )
        for candidate_id, locator in corpus.locator_by_candidate_id.items()
    }
    matches = [
        SearchMatch(candidate=candidate_by_locator[locator])
        for locator in case.historical_results[:3]
    ]

    score = score_find(case, matches, corpus)

    assert score["historical_result_recall"] == pytest.approx(3 / 5)
    assert score["historical_result_precision"] == 1.0
    assert score["study_selected_recall"] == pytest.approx(2 / 4)
    assert "accuracy" not in score


def test_query_score_covers_supported_answer_and_flags_invented_days():
    narrow_answer = (
        "Merely mentioning Memory content does not send it to the institution. "
        "Only content actually sent through the transmission screen counts, "
        "and this agent cannot delete it."
    )
    unsupported_answer = (
        "The retention period is 30 days. No named third-party company is "
        "identified by the available source."
    )

    narrow_score = score_query(QUERY_CASES[1], narrow_answer)
    unsupported_score = score_query(QUERY_CASES[2], unsupported_answer)
    supported_unsupported_answer = (
        "The available source does not specify an exact retention period or "
        "name any third-party company that receives medication information."
    )
    supported_unsupported_score = score_query(
        QUERY_CASES[2], supported_unsupported_answer
    )

    assert narrow_score["concept_recall"] == 1.0
    assert unsupported_score["forbidden_violation"] is True
    assert supported_unsupported_score["concept_recall"] == 1.0
    assert supported_unsupported_score["forbidden_violation"] is False


class _FakeProvider:
    def __init__(self, *, model: str, reasoning_effort: str):
        self.identity = ProviderIdentity(
            provider="fake",
            model=model,
            reasoning_effort=reasoning_effort,
        )
        self.timeout = 1.0
        self.last_run: CompletionRun | None = None

    def complete(self, prompt, *, operation, output_schema=None):
        self.last_run = CompletionRun(identity=self.identity, operation=operation)
        if operation == "find":
            return json.dumps(
                {"matches": [], "related_query": "", "related_matches": []}
            )
        return "The available source does not answer the question."


def _fake_connector(*, timeout, model, reasoning_effort):
    return _FakeProvider(model=model, reasoning_effort=reasoning_effort)


def test_campaign_is_atomic_and_resume_skips_completed_cells(tmp_path: Path):
    output = tmp_path / "matrix.json"
    condition = (MatrixCondition("gpt-5.6-sol", "none"),)
    cases = (FIND_CASES[2], QUERY_CASES[2])

    first = run_campaign(
        output,
        timeout=1,
        cases=cases,
        conditions=condition,
        connector=_fake_connector,
    )
    resumed = run_campaign(
        output,
        timeout=1,
        resume=True,
        cases=cases,
        conditions=condition,
        connector=_fake_connector,
    )

    assert first["status"] == "COMPLETED"
    assert len(first["attempts"]) == 2
    assert len(resumed["attempts"]) == 2
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "COMPLETED"

    rescored = rescore_campaign(output, cases=cases, conditions=condition)
    assert len(rescored["attempts"]) == 2
    assert rescored["rescoring_note"].startswith("Scoring probes")


def test_matrix_defaults_are_exact_requested_models_and_efforts():
    assert len(DEFAULT_CONDITIONS) == 9
    assert {(value.model, value.effort) for value in DEFAULT_CONDITIONS} == {
        (model, effort)
        for model in ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna")
        for effort in ("none", "low", "medium")
    }
