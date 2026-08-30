"""Core contracts for replayable calibration and holdout campaigns."""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import memcommit.application.operations.eval.semantic_campaign as campaign_module
from memcommit.application.capabilities.semantic.classification.ambiguity import AmbiguityPipelineError
from memcommit.application.operations.eval.semantic_campaign import (
    DEFAULT_AMBIGUITY_FIXTURE,
    DEFAULT_AMBIGUITY_HOLDOUT_FIXTURE,
    DEFAULT_DUPLICATE_FIXTURE,
    SemanticCampaignError,
    load_ambiguity_corpus,
    load_ambiguity_holdout_lock,
    load_campaign_ledgers,
    load_duplicate_corpus,
    run_ambiguity_campaign,
    run_duplicate_campaign,
)
from memcommit.providers.types import CompletionRun, ProviderIdentity
from memcommit.providers.subscription import QueryProviderError


class FakeClock:
    def __init__(self, values: list[float] | None = None) -> None:
        self.values = list(values) if values is not None else []
        self.next_value = 0.0

    def __call__(self) -> float:
        if self.values:
            return self.values.pop(0)
        value = self.next_value
        self.next_value += 1.0
        return value


class FakeProvider:
    def __init__(self) -> None:
        self.identity = ProviderIdentity(
            provider="ollama",
            model="qwen3.6:35b-a3b",
            model_digest="a" * 64,
            runtime="ollama/test",
            endpoint="http://127.0.0.1:11434",
        )
        self.timeout = 45.0
        self.context_tokens = 32_768
        self.max_output_tokens = 512
        self.thinking = True
        self.last_run: CompletionRun | None = None


class BinaryProvider(FakeProvider):
    def __init__(self, responses: list[str]) -> None:
        super().__init__()
        self.responses = list(responses)
        self.calls: list[str] = []

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls.append(prompt)
        self.last_run = CompletionRun(
            identity=self.identity,
            operation=operation,
            prompt_tokens=7,
            completion_tokens=2,
            upstream_model=self.identity.model,
            upstream_provider="ollama",
        )
        return self.responses.pop(0)


class SequenceClassifier:
    """Return expected labels unless an outcome overrides or raises."""

    def __init__(self, outcomes: list[object] | None = None) -> None:
        self.outcomes = list(outcomes or [])
        self.calls: list[tuple[dict[str, object], list[dict[str, object]]]] = []

    def __call__(self, case, provider, *, calibration_examples):
        self.calls.append(
            (copy.deepcopy(case), copy.deepcopy(list(calibration_examples)))
        )
        outcome = self.outcomes.pop(0) if self.outcomes else None
        if isinstance(outcome, BaseException):
            raise outcome
        expected = case["expected"]
        labels = (
            (expected["interpretation"], expected["clarification"])
            if outcome is None
            else outcome
        )
        interpretation, clarification = labels
        raw = json.dumps(
            {
                "interpretation": interpretation,
                "clarification": clarification,
            },
            separators=(",", ":"),
        )
        ordinal = len(self.calls)
        provider.last_run = CompletionRun(
            identity=provider.identity,
            operation="ambiguity classification",
            prompt_tokens=10,
            completion_tokens=4,
            upstream_model=provider.identity.model,
            upstream_provider=provider.identity.provider,
        )
        return SimpleNamespace(
            classification=SimpleNamespace(
                interpretation=interpretation,
                clarification=clarification,
            ),
            prompt_digest=hashlib.sha256(
                f"prompt-{ordinal}".encode()
            ).hexdigest(),
            schema_digest=hashlib.sha256(b"schema-v1").hexdigest(),
            response_digest=hashlib.sha256(raw.encode()).hexdigest(),
            raw_response=raw,
        )


def _fixture_data() -> dict[str, object]:
    return json.loads(DEFAULT_AMBIGUITY_FIXTURE.read_text(encoding="utf-8"))


def _write_fixture(tmp_path: Path, value: object) -> Path:
    path = tmp_path / "ambiguity.json"
    path.write_text(
        json.dumps(value, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def _run(
    tmp_path: Path,
    classifier,
    *,
    runs: int = 1,
    case_ids: list[str] | None = None,
    clock=None,
    known_error_types=(),
    progress_fn=None,
    corpus_role: str = "calibration",
):
    return run_ambiguity_campaign(
        FakeProvider(),  # type: ignore[arg-type]
        ledger_dir=tmp_path / "ledgers",
        provider_connection_seconds=0.5,
        runs=runs,
        corpus_role=corpus_role,
        classifier=classifier,
        known_error_types=known_error_types,
        case_ids=case_ids,
        clock=clock or FakeClock(),
        utcnow=lambda: datetime(2026, 8, 3, tzinfo=timezone.utc),
        progress_fn=progress_fn,
    )


def test_fixture_loader_rejects_duplicate_json_keys(tmp_path):
    fixture = tmp_path / "ambiguity.json"
    fixture.write_text(
        '{"operation":"find-ambiguities","operation":"find-ambiguities"}',
        encoding="utf-8",
    )

    with pytest.raises(SemanticCampaignError, match="strict UTF-8 JSON"):
        load_ambiguity_corpus(fixture)


def test_frozen_holdout_lock_matches_reviewed_fixture_and_calibration():
    lock = load_ambiguity_holdout_lock()
    holdout = load_ambiguity_corpus(DEFAULT_AMBIGUITY_HOLDOUT_FIXTURE)
    calibration = load_ambiguity_corpus(DEFAULT_AMBIGUITY_FIXTURE)

    assert lock.fixture == DEFAULT_AMBIGUITY_HOLDOUT_FIXTURE.name
    assert lock.fixture_digest == holdout.digest
    assert lock.case_count == len(holdout.cases) == 12
    assert lock.calibration_fixture == DEFAULT_AMBIGUITY_FIXTURE.name
    assert lock.calibration_digest == calibration.digest
    assert {case["id"] for case in holdout.cases}.isdisjoint(
        {case["id"] for case in calibration.cases}
    )


def test_holdout_uses_all_frozen_calibration_cases_and_no_holdout_examples(
    tmp_path,
):
    holdout = load_ambiguity_corpus(DEFAULT_AMBIGUITY_HOLDOUT_FIXTURE)
    calibration = load_ambiguity_corpus(DEFAULT_AMBIGUITY_FIXTURE)
    held_id = str(holdout.cases[0]["id"])
    classifier = SequenceClassifier()

    ledger = _run(
        tmp_path,
        classifier,
        case_ids=[held_id],
        corpus_role="holdout",
    )

    held, examples = classifier.calls[0]
    assert held["id"] == held_id
    assert {example["id"] for example in examples} == {
        case["id"] for case in calibration.cases
    }
    assert held_id not in {example["id"] for example in examples}
    assert ledger["corpus"]["role"] == "HOLDOUT"
    assert ledger["corpus"]["calibration_mode"] == "FIXED_CALIBRATION"
    assert ledger["corpus"]["independent_holdout"] is True
    assert ledger["corpus"]["fixture_digest"] == holdout.digest
    assert ledger["corpus"]["calibration_fixture_digest"] == calibration.digest


def test_holdout_refuses_a_fixture_changed_after_freeze(tmp_path):
    changed = json.loads(
        DEFAULT_AMBIGUITY_HOLDOUT_FIXTURE.read_text(encoding="utf-8")
    )
    changed["description"] += " changed"
    fixture = tmp_path / DEFAULT_AMBIGUITY_HOLDOUT_FIXTURE.name
    fixture.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(SemanticCampaignError, match="frozen lock"):
        run_ambiguity_campaign(
            FakeProvider(),  # type: ignore[arg-type]
            ledger_dir=tmp_path / "ledgers",
            provider_connection_seconds=0.1,
            corpus_role="holdout",
            fixture_path=fixture,
            classifier=SequenceClassifier(),
        )


def test_duplicate_campaign_decomposes_host_and_semantic_relations(tmp_path):
    provider = BinaryProvider(
        [
            '{"relation":"SEMANTIC_EQUIVALENT"}',
            '{"relation":"OVERLAP"}',
            '{"relation":"UNKNOWN"}',
            '{"relation":"DISTINCT"}',
        ]
    )

    ledger = run_duplicate_campaign(
        provider,  # type: ignore[arg-type]
        ledger_dir=tmp_path / "ledgers",
        provider_connection_seconds=0.1,
        runs=1,
        clock=FakeClock(),
        utcnow=lambda: datetime(2026, 8, 3, tzinfo=timezone.utc),
    )

    assert ledger["status"] == "COMPLETED"
    assert ledger["corpus"]["operation"] == "find-duplicates"
    assert ledger["pipeline"]["id"] == "duplicate-relation-v1"
    assert ledger["summary"]["cases"] == {
        "passed": 6,
        "failed": 0,
        "total": 6,
    }
    assert ledger["summary"]["attempts"] == {
        "exact_matches": 6,
        "structurally_valid": 6,
        "total": 6,
    }
    assert [attempt["stage"] for attempt in ledger["attempts"]] == [
        "HOST_EXACT",
        "HOST_SURFACE_EQUIVALENT",
        "SEMANTIC_RELATION",
        "SEMANTIC_RELATION",
        "SEMANTIC_RELATION",
        "SEMANTIC_RELATION",
    ]
    assert ledger["summary"]["tokens"]["reported_attempts"] == 4
    assert set(ledger["summary"]["stage_completion_seconds"]) == {
        "HOST_EXACT",
        "HOST_SURFACE_EQUIVALENT",
        "SEMANTIC_RELATION",
    }


def test_duplicate_fixture_and_semantic_leave_one_out_contract(tmp_path):
    corpus = load_duplicate_corpus(DEFAULT_DUPLICATE_FIXTURE)

    assert len(corpus.cases) == 6
    assert [case["expected"]["relation"] for case in corpus.cases] == [
        "EXACT",
        "SURFACE_EQUIVALENT",
        "SEMANTIC_EQUIVALENT",
        "OVERLAP",
        "UNKNOWN",
        "DISTINCT",
    ]
    provider = BinaryProvider(['{"relation":"SEMANTIC_EQUIVALENT"}'])
    run_duplicate_campaign(
        provider,  # type: ignore[arg-type]
        ledger_dir=tmp_path / "ledgers",
        provider_connection_seconds=0.1,
        runs=1,
        case_ids=["semantic-equivalent-paraphrase"],
        clock=FakeClock(),
        utcnow=lambda: datetime(2026, 8, 3, tzinfo=timezone.utc),
    )
    payload = json.loads(
        provider.calls[0].split("DUPLICATE RELATION PAYLOAD:\n", 1)[1]
    )
    examples = payload["calibration_examples"]
    assert {example["id"] for example in examples} == {
        "overlap-extra-cause",
        "unknown-unspecified-entrance",
        "distinct-vehicle-and-pedestrian-access",
    }
    assert all(set(example["expected"]) == {"relation"} for example in examples)
    assert "semantic-equivalent-paraphrase" not in {
        example["id"] for example in examples
    }


@pytest.mark.parametrize("mutation", ["top-level-extra", "case-shape", "duplicate-id"])
def test_fixture_loader_rejects_partial_or_ambiguous_shapes(tmp_path, mutation):
    fixture = _fixture_data()
    cases = fixture["cases"]
    if mutation == "top-level-extra":
        fixture["unexpected"] = True
    elif mutation == "case-shape":
        cases[0]["expected"]["unexpected"] = True
    else:
        cases[1]["id"] = cases[0]["id"]

    with pytest.raises(SemanticCampaignError):
        load_ambiguity_corpus(_write_fixture(tmp_path, fixture))


def test_leave_one_out_excludes_held_case_and_projects_other_nine(tmp_path):
    corpus = load_ambiguity_corpus()
    held_id = str(corpus.cases[-1]["id"])
    classifier = SequenceClassifier()

    ledger = _run(tmp_path, classifier, case_ids=[held_id])

    assert ledger["status"] == "COMPLETED"
    assert len(classifier.calls) == 1
    held, calibration = classifier.calls[0]
    assert held["id"] == held_id
    assert len(calibration) == 9
    assert held_id not in {example["id"] for example in calibration}
    assert {example["id"] for example in calibration} == {
        case["id"] for case in corpus.cases if case["id"] != held_id
    }
    assert all(
        set(example) == {"id", "scenario", "memory", "expected"}
        and set(example["expected"]) == {"interpretation", "clarification"}
        for example in calibration
    )


def test_case_subset_still_calibrates_from_full_corpus_minus_held(tmp_path):
    corpus = load_ambiguity_corpus()
    selected_ids = [str(corpus.cases[0]["id"]), str(corpus.cases[-1]["id"])]
    classifier = SequenceClassifier()

    _run(tmp_path, classifier, case_ids=selected_ids)

    assert len(classifier.calls) == 2
    all_ids = {case["id"] for case in corpus.cases}
    for held, calibration in classifier.calls:
        assert len(calibration) == 9
        assert {example["id"] for example in calibration} == all_ids - {
            held["id"]
        }


def test_pipeline_identity_is_frozen_and_v1_remains_replayable(tmp_path):
    case_id = str(load_ambiguity_corpus().cases[0]["id"])
    provider = FakeProvider()

    ledger = run_ambiguity_campaign(
        provider,  # type: ignore[arg-type]
        ledger_dir=tmp_path / "ledgers",
        provider_connection_seconds=0.1,
        runs=1,
        pipeline="v1",
        classifier=SequenceClassifier(),
        case_ids=[case_id],
        clock=FakeClock(),
        utcnow=lambda: datetime(2026, 8, 3, tzinfo=timezone.utc),
    )

    assert ledger["pipeline"]["id"] == "ambiguity-classify-v1"
    assert ledger["pipeline"]["version"] == 1

    with pytest.raises(SemanticCampaignError, match="pipeline must be one of"):
        run_ambiguity_campaign(
            provider,  # type: ignore[arg-type]
            ledger_dir=tmp_path / "invalid",
            provider_connection_seconds=0.1,
            pipeline="unknown",
        )


def test_v3_campaign_retains_stage_artifacts_timing_and_call_tokens(tmp_path):
    case_id = "single-none-main-entrance-hours"
    provider = BinaryProvider(['{"answer":"NO"}', '{"answer":"NO"}'])

    ledger = run_ambiguity_campaign(
        provider,  # type: ignore[arg-type]
        ledger_dir=tmp_path / "ledgers",
        provider_connection_seconds=0.1,
        runs=1,
        pipeline="v3",
        case_ids=[case_id],
        clock=FakeClock(),
        utcnow=lambda: datetime(2026, 8, 3, tzinfo=timezone.utc),
    )

    assert ledger["pipeline"] == {
        "id": "ambiguity-binary-v3",
        "version": 3,
        "stages": [
            "MULTIPLE_READINGS",
            "CLEAR_LEADER",
            "PRACTICAL_IMPROVEMENT",
            "CAN_PROCEED",
            "PROJECT_LABELS",
        ],
        "gate": "exact two-label contract with repeated stability",
    }
    stage_runs = ledger["attempts"][0]["stage_runs"]
    assert [stage["stage"] for stage in stage_runs] == [
        "MULTIPLE_READINGS",
        "PRACTICAL_IMPROVEMENT",
    ]
    assert set(ledger["summary"]["stage_completion_seconds"]) == {
        "MULTIPLE_READINGS",
        "PRACTICAL_IMPROVEMENT",
    }
    assert ledger["summary"]["tokens"] == {
        "prompt": 14,
        "completion": 4,
        "reported_attempts": 1,
        "reported_calls": 2,
    }


def test_v4_campaign_supplies_reviewed_evidence_only_for_other_cases(tmp_path):
    held_id = "dominant-required-entry-permit"
    classifier = SequenceClassifier()

    _run(
        tmp_path,
        classifier,
        case_ids=[held_id],
    )
    # The default injected-classifier helper exercises V2 label projection.
    assert set(classifier.calls[0][1][0]["expected"]) == {
        "interpretation",
        "clarification",
    }

    v4_classifier = SequenceClassifier()
    ledger = run_ambiguity_campaign(
        FakeProvider(),  # type: ignore[arg-type]
        ledger_dir=tmp_path / "v4-ledgers",
        provider_connection_seconds=0.1,
        runs=1,
        pipeline="v4",
        classifier=v4_classifier,
        case_ids=[held_id],
        clock=FakeClock(),
        utcnow=lambda: datetime(2026, 8, 3, tzinfo=timezone.utc),
    )

    assert ledger["pipeline"]["id"] == "ambiguity-census-v4"
    held, calibration = v4_classifier.calls[0]
    assert held["id"] == held_id
    assert held_id not in {example["id"] for example in calibration}
    assert all(
        set(example["expected"])
        == {"interpretation", "clarification", "ordinary_readings", "question"}
        for example in calibration
    )


def test_three_run_gate_accepts_two_exact_and_one_stable_mismatch(tmp_path):
    case_id = str(load_ambiguity_corpus().cases[0]["id"])
    classifier = SequenceClassifier(
        [None, ("DOMINANT", "NONE"), None]
    )

    ledger = _run(tmp_path, classifier, runs=3, case_ids=[case_id])

    result = ledger["summary"]["case_results"][0]
    assert result == {
        "case_id": case_id,
        "expected": {"interpretation": "SINGLE", "clarification": "NONE"},
        "status": "PASS",
        "attempts": 3,
        "structurally_valid": 3,
        "exact_matches": 2,
        "majority_count": 2,
        "required_count": 2,
        "stability": pytest.approx(2 / 3),
    }
    assert ledger["summary"]["campaign_passed"] is True


@pytest.mark.parametrize(
    "failure",
    [
        AmbiguityPipelineError(
            "schema mismatch",
            category="SCHEMA",
            raw_response='{"wrong":true}',
            prompt_digest="1" * 64,
            schema_digest="2" * 64,
        ),
        QueryProviderError("provider unavailable"),
    ],
)
def test_three_run_gate_fails_if_any_attempt_lacks_structured_output(
    tmp_path,
    failure,
):
    case_id = str(load_ambiguity_corpus().cases[0]["id"])
    classifier = SequenceClassifier([None, failure, None])

    ledger = _run(tmp_path, classifier, runs=3, case_ids=[case_id])

    result = ledger["summary"]["case_results"][0]
    assert result["status"] == "FAIL"
    assert result["exact_matches"] == 2
    assert result["structurally_valid"] == 2
    assert ledger["summary"]["campaign_passed"] is False
    assert len(classifier.calls) == 3


def test_declared_known_failure_is_recorded_and_campaign_continues(tmp_path):
    class KnownProviderFailure(RuntimeError):
        pass

    case_id = str(load_ambiguity_corpus().cases[0]["id"])
    classifier = SequenceClassifier(
        [KnownProviderFailure("private upstream detail"), None, None]
    )

    ledger = _run(
        tmp_path,
        classifier,
        runs=3,
        case_ids=[case_id],
        known_error_types=(KnownProviderFailure,),
    )

    assert ledger["status"] == "COMPLETED"
    assert len(classifier.calls) == 3
    assert [attempt["failure_category"] for attempt in ledger["attempts"]] == [
        "PROVIDER",
        None,
        None,
    ]
    assert ledger["attempts"][0]["diagnostic"] == (
        "A configured campaign dependency returned a known failure."
    )


def test_each_attempt_is_snapshotted_before_completed_status(
    tmp_path,
    monkeypatch,
):
    snapshots: list[dict[str, object]] = []
    atomic_write = campaign_module._atomic_write_json

    def capture(path, value):
        atomic_write(path, value)
        snapshots.append(json.loads(path.read_text(encoding="utf-8")))

    monkeypatch.setattr(campaign_module, "_atomic_write_json", capture)
    case_id = str(load_ambiguity_corpus().cases[0]["id"])

    ledger = _run(
        tmp_path,
        SequenceClassifier(),
        runs=3,
        case_ids=[case_id],
    )

    assert [snapshot["status"] for snapshot in snapshots] == [
        "RUNNING",
        "RUNNING",
        "RUNNING",
        "RUNNING",
        "COMPLETED",
    ]
    assert [len(snapshot["attempts"]) for snapshot in snapshots] == [0, 1, 2, 3, 3]
    assert ledger["status"] == "COMPLETED"
    loaded = load_campaign_ledgers(tmp_path / "ledgers")
    assert len(loaded) == 1
    assert loaded[0]["status"] == "COMPLETED"


def test_unexpected_failure_records_atomic_aborted_snapshot(tmp_path):
    case_id = str(load_ambiguity_corpus().cases[0]["id"])
    classifier = SequenceClassifier([RuntimeError("unexpected secret")])

    with pytest.raises(RuntimeError, match="unexpected secret"):
        _run(tmp_path, classifier, case_ids=[case_id])

    loaded = load_campaign_ledgers(tmp_path / "ledgers")
    assert len(loaded) == 1
    ledger = loaded[0]
    assert ledger["status"] == "ABORTED"
    assert ledger["completed_at"] is not None
    assert len(ledger["attempts"]) == 1
    assert ledger["attempts"][0]["failure_category"] == "INTERNAL"
    assert ledger["attempts"][0]["diagnostic"] == (
        "The host campaign aborted on an unexpected internal failure."
    )


def test_timing_identity_tokens_and_retained_artifacts(tmp_path):
    case_id = str(load_ambiguity_corpus().cases[0]["id"])
    clock = FakeClock([0.0, 1.0, 2.0, 3.0, 5.0, 6.0, 10.0, 12.0])

    ledger = _run(
        tmp_path,
        SequenceClassifier(),
        runs=3,
        case_ids=[case_id],
        clock=clock,
    )

    assert ledger["timing"] == {
        "provider_connection_seconds": 0.5,
        "campaign_seconds": 12.0,
        "total_seconds": 12.5,
    }
    assert [attempt["completion_seconds"] for attempt in ledger["attempts"]] == [
        1.0,
        2.0,
        4.0,
    ]
    latency = ledger["summary"]["completion_seconds"]
    assert latency["mean"] == pytest.approx(7 / 3)
    assert latency["median"] == 2.0
    assert latency["p95"] == 4.0
    assert latency["max"] == 4.0
    assert ledger["provider"] == {
        "provider": "ollama",
        "model": "qwen3.6:35b-a3b",
        "model_digest": "a" * 64,
        "runtime": "ollama/test",
        "endpoint": "http://127.0.0.1:11434",
        "reasoning_effort": None,
        "effective_thinking": True,
    }
    assert ledger["summary"]["tokens"] == {
        "prompt": 30,
        "completion": 12,
        "reported_attempts": 3,
        "reported_calls": 3,
    }
    for attempt in ledger["attempts"]:
        assert "prompt" not in attempt
        assert attempt["raw_response"]
        assert len(attempt["prompt_digest"]) == 64
        assert len(attempt["schema_digest"]) == 64
        assert attempt["response_digest"] == hashlib.sha256(
            attempt["raw_response"].encode()
        ).hexdigest()
        assert attempt["provider_run"] == {
            "operation": "ambiguity classification",
            "prompt_tokens": 10,
            "completion_tokens": 4,
            "upstream_model": "qwen3.6:35b-a3b",
            "upstream_provider": "ollama",
        }


def test_load_campaign_ledgers_rejects_corrupt_strict_json(tmp_path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "broken.json").write_text(
        '{"schema_version":1,"schema_version":1}',
        encoding="utf-8",
    )

    with pytest.raises(SemanticCampaignError, match="invalid strict JSON"):
        load_campaign_ledgers(tmp_path)


def test_load_campaign_ledgers_rejects_symlink_entry(tmp_path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    (runs_dir / "linked.json").symlink_to(target)

    with pytest.raises(SemanticCampaignError, match="Unexpected semantic ledger entry"):
        load_campaign_ledgers(tmp_path)
