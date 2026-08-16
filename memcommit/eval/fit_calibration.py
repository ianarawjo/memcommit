"""Strict consumed-calibration corpus and runner for general Fit.

The reviewed expectations are evaluation evidence only.  They never enter the
production Fit prompt: the runner supplies only each frozen background and
proposition frame, then scores the returned closed-label judgment locally.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from memcommit.fit_judgment import (
    FitBatchAnalysis,
    FitJudgmentProvider,
    FitProposition,
    FitQuestion,
    FitVerdict,
    execute_fit_judgments,
    prepare_fit_judgments,
)


FIT_CALIBRATION_SCHEMA_VERSION = 1
FIT_CALIBRATION_RULESET_VERSION = "fit-ordinary-reader-v1"
FIT_CALIBRATION_CORPUS_ROLE = "CONSUMED_CALIBRATION"
FIT_CALIBRATION_LABELS = ("YES", "MAY", "NO")
DEFAULT_FIT_CALIBRATION_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "fit.json"
)


class FitCalibrationError(ValueError):
    """The reviewed Fit corpus or one calibration run is invalid."""


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise FitCalibrationError(f"Duplicate Fit calibration JSON key: {key}.")
        result[key] = value
    return result


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FitCalibrationError(f"Fit calibration {label} must be nonblank text.")
    return value.strip()


@dataclass(frozen=True)
class FitCalibrationCase:
    """One reviewed ordinary-reading boundary without prompt-visible gold."""

    case_id: str
    scenario: str
    question: FitQuestion
    expected_verdict: FitVerdict
    expected_rationale: str


@dataclass(frozen=True)
class FitCalibrationCorpus:
    path: Path
    digest: str
    ruleset_version: str
    cases: tuple[FitCalibrationCase, ...]


@dataclass(frozen=True)
class FitCalibrationCaseResult:
    case_id: str
    expected_verdict: FitVerdict
    actual_verdict: FitVerdict
    matched: bool
    provider_reason: str


@dataclass(frozen=True)
class FitCalibrationRun:
    corpus_digest: str
    ruleset_version: str
    analysis: FitBatchAnalysis
    cases: tuple[FitCalibrationCaseResult, ...]

    @property
    def matched_count(self) -> int:
        return sum(case.matched for case in self.cases)

    @property
    def total_count(self) -> int:
        return len(self.cases)

    @property
    def exact_label_rate(self) -> float:
        return self.matched_count / self.total_count


def _proposition(value: object, *, label: str) -> FitProposition:
    if not isinstance(value, dict) or set(value) != {"alias", "role", "content"}:
        raise FitCalibrationError(f"Fit calibration {label} has invalid fields.")
    try:
        return FitProposition(
            alias=_text(value["alias"], f"{label} alias"),
            role=_text(value["role"], f"{label} role"),  # type: ignore[arg-type]
            content=_text(value["content"], f"{label} content"),
        )
    except (TypeError, ValueError) as error:
        raise FitCalibrationError(f"Fit calibration {label} is invalid.") from error


def _case(value: object, *, index: int) -> FitCalibrationCase:
    if not isinstance(value, dict) or set(value) != {
        "id",
        "scenario",
        "background",
        "propositions",
        "expected",
    }:
        raise FitCalibrationError(
            f"Fit calibration case {index} has an invalid field set."
        )
    case_id = _text(value["id"], f"case {index} id")
    scenario = _text(value["scenario"], f"case {case_id} scenario")
    background = value["background"]
    propositions = value["propositions"]
    if not isinstance(background, list) or not isinstance(propositions, list):
        raise FitCalibrationError(
            f"Fit calibration case {case_id} frames must be arrays."
        )
    expected = value["expected"]
    if not isinstance(expected, dict) or set(expected) != {"verdict", "rationale"}:
        raise FitCalibrationError(
            f"Fit calibration case {case_id} has an invalid expectation."
        )
    verdict = expected["verdict"]
    if verdict not in FIT_CALIBRATION_LABELS:
        raise FitCalibrationError(
            f"Fit calibration case {case_id} has an invalid verdict."
        )
    try:
        question = FitQuestion(
            question_id=case_id,
            background=tuple(
                _proposition(item, label=f"case {case_id} background {item_index}")
                for item_index, item in enumerate(background, 1)
            ),
            propositions=tuple(
                _proposition(item, label=f"case {case_id} proposition {item_index}")
                for item_index, item in enumerate(propositions, 1)
            ),
        )
    except (TypeError, ValueError) as error:
        raise FitCalibrationError(
            f"Fit calibration case {case_id} has an invalid Fit frame."
        ) from error
    return FitCalibrationCase(
        case_id=case_id,
        scenario=scenario,
        question=question,
        expected_verdict=verdict,  # type: ignore[arg-type]
        expected_rationale=_text(
            expected["rationale"],
            f"case {case_id} expected rationale",
        ),
    )


def load_fit_calibration(
    path: Path | None = None,
) -> FitCalibrationCorpus:
    """Load the reviewed Fit calibration without accepting partial shapes."""

    fixture_path = path or DEFAULT_FIT_CALIBRATION_FIXTURE
    try:
        raw_bytes = fixture_path.read_bytes()
        value = json.loads(
            raw_bytes.decode("utf-8"),
            object_pairs_hook=_strict_object,
        )
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise FitCalibrationError(
            "The Fit calibration fixture is not valid strict UTF-8 JSON."
        ) from error
    if not isinstance(value, dict) or set(value) != {
        "operation",
        "schema_version",
        "ruleset_version",
        "corpus_role",
        "independent_holdout",
        "description",
        "labels",
        "cases",
    }:
        raise FitCalibrationError(
            "The Fit calibration fixture has an invalid top-level contract."
        )
    if (
        value["operation"] != "fit"
        or value["schema_version"] != FIT_CALIBRATION_SCHEMA_VERSION
        or isinstance(value["schema_version"], bool)
        or value["ruleset_version"] != FIT_CALIBRATION_RULESET_VERSION
        or value["corpus_role"] != FIT_CALIBRATION_CORPUS_ROLE
        or value["independent_holdout"] is not False
        or value["labels"] != list(FIT_CALIBRATION_LABELS)
    ):
        raise FitCalibrationError(
            "The Fit calibration fixture identity or label contract is unsupported."
        )
    _text(value["description"], "description")
    raw_cases = value["cases"]
    if not isinstance(raw_cases, list) or not raw_cases:
        raise FitCalibrationError("The Fit calibration fixture is empty.")
    cases = tuple(_case(case, index=index) for index, case in enumerate(raw_cases, 1))
    case_ids = tuple(case.case_id for case in cases)
    if len(case_ids) != len(set(case_ids)):
        raise FitCalibrationError("Fit calibration case ids must be unique.")
    observed_labels = {case.expected_verdict for case in cases}
    if observed_labels != set(FIT_CALIBRATION_LABELS):
        raise FitCalibrationError(
            "Fit calibration must contain every YES/MAY/NO boundary."
        )
    return FitCalibrationCorpus(
        path=fixture_path,
        digest=hashlib.sha256(raw_bytes).hexdigest(),
        ruleset_version=FIT_CALIBRATION_RULESET_VERSION,
        cases=cases,
    )


def run_fit_calibration(
    corpus: FitCalibrationCorpus,
    *,
    provider: FitJudgmentProvider,
) -> FitCalibrationRun:
    """Judge every reviewed case in one whole-frame call and score labels locally."""

    if not isinstance(corpus, FitCalibrationCorpus):
        raise TypeError("Fit calibration requires a typed corpus.")
    prepared = prepare_fit_judgments(tuple(case.question for case in corpus.cases))
    analysis = execute_fit_judgments(prepared, provider=provider)
    results = tuple(
        FitCalibrationCaseResult(
            case_id=case.case_id,
            expected_verdict=case.expected_verdict,
            actual_verdict=assessment.verdict,
            matched=case.expected_verdict == assessment.verdict,
            provider_reason=assessment.reason,
        )
        for case, assessment in zip(corpus.cases, analysis.assessments, strict=True)
    )
    return FitCalibrationRun(
        corpus_digest=corpus.digest,
        ruleset_version=corpus.ruleset_version,
        analysis=analysis,
        cases=results,
    )


__all__ = [
    "DEFAULT_FIT_CALIBRATION_FIXTURE",
    "FIT_CALIBRATION_CORPUS_ROLE",
    "FIT_CALIBRATION_LABELS",
    "FIT_CALIBRATION_RULESET_VERSION",
    "FIT_CALIBRATION_SCHEMA_VERSION",
    "FitCalibrationCase",
    "FitCalibrationCaseResult",
    "FitCalibrationCorpus",
    "FitCalibrationError",
    "FitCalibrationRun",
    "load_fit_calibration",
    "run_fit_calibration",
]
