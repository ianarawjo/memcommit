"""Contracts for the strict-boundary Task 2 judge replay V6 ablation."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

import pytest

import memcommit.eval.task2_judge_replay_v5 as judge_v5
import memcommit.eval.task2_judge_replay_v6 as judge_v6
import memcommit.eval.task2_retrieval_v4 as retrieval_v4
from memcommit.eval.task2_discovery import (
    build_task2_discovery_input,
    load_task2_discovery_corpus,
)
from memcommit.eval.task2_retrieval_v4 import (
    CANDIDATE_STAGE,
    LEFT_TO_RIGHT,
    VERIFIER_STAGE,
    run_task2_retrieval_v4_campaign,
)
from memcommit.provider_types import CompletionRun, ProviderIdentity


class V4ParentTeacher:
    """Produce two distinct, contract-valid V4 candidate parents."""

    def __init__(self, value, *, reverse_fillers: bool) -> None:
        self.identity = ProviderIdentity(
            provider=("v6-parent-reverse" if reverse_fillers else "v6-parent-forward"),
            model="fixture-teacher",
            model_digest=("6" if reverse_fillers else "5") * 64,
            runtime="pytest",
        )
        self.thinking = "off"
        self.last_run: CompletionRun | None = None
        self.reverse_fillers = reverse_fillers
        self.left_fixture_by_text = {
            (item["topic"], item["content"]): value.alias_to_fixture_id[item["id"]]
            for item in value.left_items
        }
        self.right_fixture_by_text = {
            (item["topic"], item["content"]): value.alias_to_fixture_id[item["id"]]
            for item in value.right_items
        }
        self.expected: dict[str, frozenset[str]] = {}
        for relation in value.expected:
            left = frozenset(relation.left_fixture_ids)
            right = frozenset(relation.right_fixture_ids)
            self.expected.update({member: right for member in left})
            self.expected.update({member: left for member in right})

    def _fixture(self, item, *, side: str) -> str:
        mapping = (
            self.left_fixture_by_text if side == "left" else self.right_fixture_by_text
        )
        return mapping[(item["topic"], item["content"])]

    def complete(self, prompt, *, operation, output_schema=None):
        payload = json.loads(prompt.split(retrieval_v4._PAYLOAD_MARKER, 1)[1])
        source_side, target_side = (
            ("left", "right")
            if payload["direction"] == LEFT_TO_RIGHT
            else ("right", "left")
        )
        selections = []
        if payload["stage"] == CANDIDATE_STAGE:
            targets = payload["targets"]
            for source in payload["sources"]:
                expected = self.expected[self._fixture(source, side=source_side)]
                by_fixture = {
                    self._fixture(target, side=target_side): target["id"]
                    for target in targets
                }
                selected = [by_fixture[item] for item in sorted(expected)]
                fillers = [
                    target["id"]
                    for target in targets
                    if target["id"] not in selected
                ]
                if self.reverse_fillers:
                    fillers.reverse()
                selections.append(
                    {
                        "source_id": source["id"],
                        "target_ids": (selected + fillers)[:3],
                    }
                )
        elif payload["stage"] == VERIFIER_STAGE:
            for source in payload["sources"]:
                expected = self.expected[self._fixture(source, side=source_side)]
                selections.append(
                    {
                        "source_id": source["id"],
                        "target_ids": [
                            target["id"]
                            for target in source["candidates"]
                            if self._fixture(target, side=target_side) in expected
                        ],
                    }
                )
        else:  # pragma: no cover - frozen V4 prompt
            raise AssertionError(payload["stage"])
        response = json.dumps({"selections": selections})
        self.last_run = CompletionRun(
            identity=self.identity,
            operation=operation,
            prompt_tokens=len(prompt.split()),
            completion_tokens=len(response.split()),
        )
        return response


class RecordingJudgeTeacher:
    """Return exact labels while recording the prompt-ablation call surface."""

    def __init__(self, value, *, fail_at: int | None = None) -> None:
        self.identity = ProviderIdentity(
            provider="v6-judge-teacher",
            model="fixture-teacher",
            model_digest="7" * 64,
            runtime="pytest",
        )
        self.thinking = "off"
        self.last_run: CompletionRun | None = None
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []
        self.fail_at = fail_at
        self.fixture_by_text = {
            (item["topic"], item["content"]): value.alias_to_fixture_id[item["id"]]
            for item in (*value.left_items, *value.right_items)
        }
        self.expected: dict[str, tuple[frozenset[str], str]] = {}
        for relation in value.expected:
            left = frozenset(relation.left_fixture_ids)
            right = frozenset(relation.right_fixture_ids)
            label = judge_v5._BAND_TO_LABEL[relation.band]
            self.expected.update({member: (right, label) for member in left})
            self.expected.update({member: (left, label) for member in right})

    def complete(self, prompt, *, operation, output_schema=None):
        call_index = len(self.calls)
        self.calls.append((prompt, operation, output_schema))
        if call_index == self.fail_at:
            raise TimeoutError("private provider endpoint")
        payload = json.loads(prompt.split(judge_v5._PAYLOAD_MARKER, 1)[1])
        judgments = []
        for pair in payload["pairs"]:
            source = self.fixture_by_text[
                (pair["source"]["topic"], pair["source"]["content"])
            ]
            target = self.fixture_by_text[
                (pair["target"]["topic"], pair["target"]["content"])
            ]
            counterparts, label = self.expected[source]
            judgments.append(
                {
                    "pair_id": pair["pair_id"],
                    "label": label if target in counterparts else "UNRELATED",
                }
            )
        response = json.dumps({"judgments": judgments})
        self.last_run = CompletionRun(
            identity=self.identity,
            operation=operation,
            prompt_tokens=len(prompt.split()),
            completion_tokens=len(response.split()),
        )
        return response


class DivergentJudgeTeacher(RecordingJudgeTeacher):
    """Flip exactly one enum across the accepted/rejected boundary."""

    def complete(self, prompt, *, operation, output_schema=None):
        is_first = not self.calls
        response = super().complete(
            prompt, operation=operation, output_schema=output_schema
        )
        if not is_first:
            return response
        decoded = json.loads(response)
        current = decoded["judgments"][0]["label"]
        decoded["judgments"][0]["label"] = (
            "CONFLICT" if current == "UNRELATED" else "UNRELATED"
        )
        return json.dumps(decoded)


@pytest.fixture(scope="module")
def parent_records(tmp_path_factory):
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=26
    )
    ledger_dir = tmp_path_factory.mktemp("task2-judge-v6-parents")
    records = [
        run_task2_retrieval_v4_campaign(
            V4ParentTeacher(value, reverse_fillers=reverse),  # type: ignore[arg-type]
            ledger_dir=ledger_dir,
            provider_connection_seconds=0.0,
            group_count=26,
        )
        for reverse in (False, True)
    ]
    return value, records


def _payloads(provider: RecordingJudgeTeacher) -> list[dict[str, object]]:
    return [
        json.loads(prompt.split(judge_v5._PAYLOAD_MARKER, 1)[1])
        for prompt, _operation, _schema in provider.calls
    ]


def test_v6_reuses_identical_v5_bundle_schedule_schema_and_scoring(parent_records):
    value, records = parent_records
    v5_input = judge_v5.build_task2_judge_replay_v5_input(records)
    v6_input = judge_v6.build_task2_judge_replay_v6_input(records)
    assert v6_input == v5_input
    assert v6_input.candidate_pairs == v5_input.candidate_pairs
    assert v6_input.candidate_bundle_digest == v5_input.candidate_bundle_digest
    assert v6_input.replay_freeze_digest == v5_input.replay_freeze_digest

    v5_provider = RecordingJudgeTeacher(value)
    v6_provider = RecordingJudgeTeacher(value)
    v5_run = judge_v5.judge_task2_candidate_union_v5(
        v5_provider, v5_input  # type: ignore[arg-type]
    )
    v6_run = judge_v6.judge_task2_candidate_union_v6(
        v6_provider, v6_input  # type: ignore[arg-type]
    )

    assert _payloads(v5_provider) == _payloads(v6_provider)
    assert [call.pair_fixture_keys for call in v6_run.calls] == [
        call.pair_fixture_keys for call in v5_run.calls
    ]
    assert [call.pair_start for call in v6_run.calls] == [
        call.pair_start for call in v5_run.calls
    ]
    assert [call.pair_stop for call in v6_run.calls] == [
        call.pair_stop for call in v5_run.calls
    ]
    assert [call.schema_digest for call in v6_run.calls] == [
        call.schema_digest for call in v5_run.calls
    ]
    assert [call.local_id_mapping_digest for call in v6_run.calls] == [
        call.local_id_mapping_digest for call in v5_run.calls
    ]
    assert v6_run.score == v5_run.score
    assert v6_run.score["binary_same_hypergroup"]["accuracy"] == 1.0
    assert v6_run.score["multi_member_binary"]["recall"] == 1.0
    assert v6_run.score["source_accepted_set"]["exact_accuracy"] == 1.0
    assert v6_run.provider_call_count == math.ceil(
        len(v6_input.candidate_pairs) / judge_v6.TASK2_JUDGE_REPLAY_V6_BATCH_SIZE
    )
    assert all("task2 v5" in call[1] for call in v5_provider.calls)
    assert all("task2 v6 strict-boundary" in call[1] for call in v6_provider.calls)


def test_v5_prompt_is_pinned_while_v6_has_explicit_two_step_boundaries():
    local_pairs = [
        {
            "pair_id": "p01",
            "source": {"topic": "t", "content": "a"},
            "target": {"topic": "t", "content": "b"},
        }
    ]
    old_prompt = judge_v5._prompt(local_pairs)
    strict_prompt = judge_v6._prompt(local_pairs)

    # This pins the V5 pre-ablation prompt: V6 must never be implemented by
    # rewriting the old prompt or changing retained V5 ledger semantics.
    assert hashlib.sha256(old_prompt.encode()).hexdigest() == (
        "a05da28af356c84a34a1f27ba343984eb08d2d8f936b534ad32c91b5ebc12194"
    )
    assert "STEP 1 — RELATIONSHIP-UNIT TEST" not in old_prompt
    assert "STEP 1 — RELATIONSHIP-UNIT TEST" in strict_prompt
    assert "STEP 2 — RELATIONSHIP ENUM" in strict_prompt
    assert "independently mergeable or independently reviewable" in strict_prompt
    for rejected_shortcut in (
        "Broad topic similarity alone",
        "adjacent-section usefulness",
        "generic compatibility",
        "shared vocabulary alone",
    ):
        assert rejected_shortcut in strict_prompt
    assert "conflicts remain accepted relationships" in strict_prompt
    assert "genuine joint parts remain accepted relationships" in strict_prompt
    assert "[UNRELATED—shared vocabulary]" in strict_prompt
    assert "[UNRELATED—adjacent usefulness]" in strict_prompt
    assert "[UNRELATED—generic compatibility]" in strict_prompt
    assert "Require two approvers before a production deployment" in strict_prompt
    assert "candidate_schedule_identical_to_v5" not in strict_prompt
    assert hashlib.sha256(
        judge_v6._STRICT_PROMPT_PREAMBLE.encode()
    ).hexdigest() == judge_v6.TASK2_JUDGE_REPLAY_V6_PROMPT_PROTOCOL_DIGEST


def test_provider_failure_continues_full_v6_schedule_and_retains_metrics(
    parent_records, tmp_path
):
    value, records = parent_records
    replay = judge_v6.build_task2_judge_replay_v6_input(records)
    provider = RecordingJudgeTeacher(value, fail_at=1)

    with pytest.raises(judge_v6.Task2JudgeReplayV6ResponseError) as captured:
        judge_v6.judge_task2_candidate_union_v6(
            provider,  # type: ignore[arg-type]
            replay,
            known_error_types=(TimeoutError,),
        )

    failed_run = captured.value.run
    assert len(provider.calls) == failed_run.provider_call_count
    assert failed_run.provider_call_count == failed_run.expected_provider_call_count
    assert failed_run.calls[1].failure_category == "PROVIDER"
    assert failed_run.calls[1].error_type == "TimeoutError"
    assert all(call.response_contract_valid for call in failed_run.calls[2:])
    assert "private provider endpoint" not in str(captured.value)
    assert set(failed_run.score) >= {
        "candidate_ceiling",
        "binary_same_hypergroup",
        "multi_member_binary",
        "group_induced_enum",
        "reviewed_one_to_one_direct_subset",
        "reviewed_one_to_one_source_set",
        "source_accepted_set",
        "pairs",
    }
    binary = failed_run.score["binary_same_hypergroup"]
    assert binary["missing_positive"] + binary["missing_negative"] == (
        failed_run.calls[1].pair_count
    )

    campaign_provider = RecordingJudgeTeacher(value, fail_at=1)
    record = judge_v6.run_task2_judge_replay_v6_campaign(
        campaign_provider,  # type: ignore[arg-type]
        parent_ledgers=records,
        ledger_dir=tmp_path,
        provider_connection_seconds=0.25,
        known_error_types=(TimeoutError,),
    )
    assert record["kind"] == judge_v6.TASK2_JUDGE_REPLAY_V6_KIND
    assert record["pipeline"] == judge_v6.TASK2_JUDGE_REPLAY_V6_PIPELINE
    assert record["status"] == "PROVIDER_ERROR"
    assert record["contract_valid"] is False
    assert record["candidate_bundle"]["digest"] == replay.candidate_bundle_digest
    assert record["candidate_bundle"]["replay_freeze_digest"] == (
        replay.replay_freeze_digest
    )
    assert record["prompt_ablation"] == {
        "baseline_kind": judge_v5.TASK2_JUDGE_REPLAY_V5_KIND,
        "baseline_pipeline": judge_v5.TASK2_JUDGE_REPLAY_V5_PIPELINE,
        "candidate_schedule_identical_to_v5": True,
        "response_schema_identical_to_v5": True,
        "prompt_revision": judge_v6.TASK2_JUDGE_REPLAY_V6_PROMPT_REVISION,
        "prompt_protocol_digest": (
            judge_v6.TASK2_JUDGE_REPLAY_V6_PROMPT_PROTOCOL_DIGEST
        ),
        "ablation_freeze_digest": failed_run.ablation_freeze_digest,
        "decision_boundary": "INDEPENDENT_RELATIONSHIP_UNIT_BEFORE_ENUM",
    }
    ledger_path = Path(record["ledger_path"])
    assert ledger_path.parent.name == "task2-judge-replay-v6"
    assert ledger_path.exists()
    assert "private provider endpoint" not in ledger_path.read_text()


def test_strict_v6_comparator_reports_exact_and_divergent_parity(
    parent_records, tmp_path
):
    value, records = parent_records
    first = judge_v6.run_task2_judge_replay_v6_campaign(
        RecordingJudgeTeacher(value),  # type: ignore[arg-type]
        parent_ledgers=records,
        ledger_dir=tmp_path,
        provider_connection_seconds=0.0,
    )
    second = judge_v6.run_task2_judge_replay_v6_campaign(
        RecordingJudgeTeacher(value),  # type: ignore[arg-type]
        parent_ledgers=records,
        ledger_dir=tmp_path,
        provider_connection_seconds=0.0,
    )
    exact = judge_v6.compare_task2_judge_replay_v6_records(first, second)

    assert exact["fixed_call_inputs_identical"] is True
    assert exact["prompt_revision"] == (
        judge_v6.TASK2_JUDGE_REPLAY_V6_PROMPT_REVISION
    )
    assert exact["prompt_protocol_digest"] == (
        judge_v6.TASK2_JUDGE_REPLAY_V6_PROMPT_PROTOCOL_DIGEST
    )
    assert exact["ablation_freeze_digest"] == first["prompt_ablation"][
        "ablation_freeze_digest"
    ]
    assert exact["exact_enum_agreement"]["exact_accuracy"] == 1.0
    assert exact["binary_accept_reject_agreement"]["exact_accuracy"] == 1.0
    assert exact["source_accepted_set_agreement"]["exact_accuracy"] == 1.0
    assert exact["multi_member_agreement"]["pair_enum"]["exact_accuracy"] == 1.0
    assert exact["multi_member_agreement"]["pair_binary_accept_reject"][
        "exact_accuracy"
    ] == 1.0
    assert exact["multi_member_agreement"]["source_accepted_set"][
        "exact_accuracy"
    ] == 1.0
    quadrants = exact["reviewed_one_to_one_direct_enum_quadrants"]
    assert sum(
        quadrants[name]
        for name in (
            "both_gold",
            "first_only_gold",
            "second_only_gold",
            "both_wrong_same",
            "both_wrong_different",
        )
    ) == quadrants["recovered_directed_sources"]
    assert exact["parity_gate"]["passed"] is True
    assert exact["trust_boundary"] == (
        "UNSIGNED_LEDGER_CONSISTENCY_CHECK_NOT_CRYPTOGRAPHIC_AUTHENTICITY"
    )

    divergent = judge_v6.run_task2_judge_replay_v6_campaign(
        DivergentJudgeTeacher(value),  # type: ignore[arg-type]
        parent_ledgers=records,
        ledger_dir=tmp_path,
        provider_connection_seconds=0.0,
    )
    parity = judge_v6.compare_task2_judge_replay_v6_records(first, divergent)
    assert parity["exact_enum_agreement"]["exact"] == parity["pair_count"] - 1
    assert parity["binary_accept_reject_agreement"]["exact"] == (
        parity["pair_count"] - 1
    )
    assert parity["source_accepted_set_agreement"]["exact"] == (
        parity["source_accepted_set_agreement"]["total"] - 1
    )
    assert parity["parity_gate"]["passed"] is False


def test_strict_v6_comparator_reconstructs_every_retained_boundary(
    parent_records, tmp_path
):
    value, records = parent_records
    first = judge_v6.run_task2_judge_replay_v6_campaign(
        RecordingJudgeTeacher(value),  # type: ignore[arg-type]
        parent_ledgers=records,
        ledger_dir=tmp_path,
        provider_connection_seconds=0.0,
    )
    second = judge_v6.run_task2_judge_replay_v6_campaign(
        RecordingJudgeTeacher(value),  # type: ignore[arg-type]
        parent_ledgers=records,
        ledger_dir=tmp_path,
        provider_connection_seconds=0.0,
    )

    mutations = [
        (
            lambda record: record["prompt_ablation"].__setitem__(
                "prompt_protocol_digest", "a" * 64
            ),
            "prompt protocol boundary",
        ),
        (
            lambda record: record["prompt_ablation"].__setitem__(
                "ablation_freeze_digest", "b" * 64
            ),
            "ablation freeze digest",
        ),
        (
            lambda record: record["calls"][0].__setitem__(
                "prompt_digest", "c" * 64
            ),
            "V6 prompt evidence",
        ),
        (
            lambda record: record["calls"][0].__setitem__(
                "schema_digest", "d" * 64
            ),
            "call evidence",
        ),
        (
            lambda record: record["calls"][0].__setitem__(
                "raw_response", record["calls"][0]["raw_response"] + " "
            ),
            "call evidence",
        ),
        (
            lambda record: record["decisions"][0].__setitem__(
                "label",
                (
                    "CONFLICT"
                    if record["decisions"][0]["label"] == "UNRELATED"
                    else "UNRELATED"
                ),
            ),
            "top-level decisions",
        ),
        (
            lambda record: record["score"]["binary_same_hypergroup"].__setitem__(
                "accuracy", 0.0
            ),
            "retained score",
        ),
        (
            lambda record: record["timing"].__setitem__(
                "total_seconds", record["timing"]["total_seconds"] + 1.0
            ),
            "campaign timing",
        ),
        (
            lambda record: record["provider_run"]["identity"].__setitem__(
                "model", "tampered-model"
            ),
            "provider_run identity disagrees",
        ),
        (
            lambda record: record["calls"][0]["provider_run"].__setitem__(
                "operation", "wrong operation"
            ),
            "operation is invalid",
        ),
        (
            lambda record: record["calibration_boundary"].__setitem__(
                "independent_holdout", True
            ),
            "calibration boundary",
        ),
    ]
    for mutate, expected_message in mutations:
        altered = copy.deepcopy(second)
        mutate(altered)
        with pytest.raises(
            judge_v6.Task2JudgeReplayV6Error, match=expected_message
        ):
            judge_v6.compare_task2_judge_replay_v6_records(first, altered)
