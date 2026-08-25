"""Executable theory checks for the general Fit calibration corpus."""

from __future__ import annotations

import json

import pytest

from memcommit.eval.fit_calibration import (
    FIT_CALIBRATION_CORPUS_ROLE,
    FitCalibrationError,
    load_fit_calibration,
    run_fit_calibration,
)
from memcommit.operations.fit.judgment import FIT_JUDGMENT_PAYLOAD_MARKER


def test_fit_calibration_is_balanced_reviewed_consumed_corpus() -> None:
    corpus = load_fit_calibration()

    counts = {
        verdict: sum(case.expected_verdict == verdict for case in corpus.cases)
        for verdict in ("YES", "MAY", "NO")
    }
    assert len(corpus.cases) == 18
    assert counts == {"YES": 6, "MAY": 6, "NO": 6}
    assert len(corpus.digest) == 64
    assert any(len(case.question.propositions) == 3 for case in corpus.cases)
    assert any(
        proposition.role == "GOAL"
        for case in corpus.cases
        for proposition in case.question.propositions
    )
    assert any(
        "그 출입구" in proposition.content
        for case in corpus.cases
        for proposition in case.question.propositions
    )
    assert FIT_CALIBRATION_CORPUS_ROLE == "CONSUMED_CALIBRATION"


class CalibrationProvider:
    def __init__(self, expected: dict[str, str], *, wrong: str | None = None) -> None:
        self.expected = expected
        self.wrong = wrong
        self.calls = 0
        self.prompt = ""

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls += 1
        self.prompt = prompt
        assert operation == "fit_propositions"
        assert output_schema is not None
        payload = json.loads(prompt.split(FIT_JUDGMENT_PAYLOAD_MARKER, 1)[1])
        judgments = []
        for question in payload["questions"]:
            question_id = question["question_id"]
            verdict = self.expected[question_id]
            if question_id == self.wrong:
                verdict = "NO" if verdict != "NO" else "YES"
            aliases = [
                item["proposition_id"]
                for item in (*question["background"], *question["propositions"])
            ]
            judgments.append(
                {
                    "question_id": question_id,
                    "verdict": verdict,
                    "reason": "One complete reviewed boundary was judged.",
                    "considered_proposition_ids": aliases,
                    "material_proposition_ids": [] if verdict == "YES" else aliases,
                    "consistent_reading": (
                        "One ordinary reading is compatible." if verdict == "MAY" else ""
                    ),
                    "inconsistent_reading": (
                        "Another ordinary reading is incompatible."
                        if verdict == "MAY"
                        else ""
                    ),
                }
            )
        return json.dumps(
            {"overview": "All calibration frames were judged.", "judgments": judgments}
        )


def test_fit_calibration_runs_once_without_putting_gold_in_prompt() -> None:
    corpus = load_fit_calibration()
    provider = CalibrationProvider(
        {case.case_id: case.expected_verdict for case in corpus.cases}
    )

    result = run_fit_calibration(corpus, provider=provider)

    assert provider.calls == 1
    assert result.matched_count == result.total_count == 18
    assert result.exact_label_rate == 1.0
    payload = json.loads(
        provider.prompt.split(FIT_JUDGMENT_PAYLOAD_MARKER, 1)[1]
    )
    assert len(payload["questions"]) == 18
    assert "expected" not in provider.prompt
    assert all("scenario" not in question for question in payload["questions"])
    assert "CONSUMED_CALIBRATION" not in provider.prompt


def test_fit_calibration_reports_mismatch_without_rewriting_provider_result() -> None:
    corpus = load_fit_calibration()
    failed_id = corpus.cases[0].case_id
    provider = CalibrationProvider(
        {case.case_id: case.expected_verdict for case in corpus.cases},
        wrong=failed_id,
    )

    result = run_fit_calibration(corpus, provider=provider)

    assert result.matched_count == 17
    failed = next(case for case in result.cases if case.case_id == failed_id)
    assert failed.matched is False
    assert failed.actual_verdict != failed.expected_verdict


def test_fit_calibration_rejects_partial_or_duplicate_contract(tmp_path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"operation":"fit","operation":"fit"}', encoding="utf-8")

    with pytest.raises(FitCalibrationError, match="strict UTF-8 JSON"):
        load_fit_calibration(duplicate)
