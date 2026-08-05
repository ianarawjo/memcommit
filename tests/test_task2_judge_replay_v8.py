"""Focused contracts for the hierarchical canonical Task 2 V8 harness."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import math

import pytest

import memcommit.eval.task2_judge_replay_v5 as judge_v5
import memcommit.eval.task2_judge_replay_v7 as judge_v7
import memcommit.eval.task2_judge_replay_v8 as judge_v8
from memcommit.eval.task2_discovery import (
    build_task2_discovery_input,
    load_task2_discovery_corpus,
)
from memcommit.eval.task2_retrieval_v4 import run_task2_retrieval_v4_campaign
from memcommit.provider_types import CompletionRun, ProviderIdentity
from tests.test_task2_judge_replay_v7 import V4ParentTeacher


class HierarchicalTeacher:
    """Return exact stage-local choices while seeing call-local IDs only."""

    def __init__(
        self,
        value,
        *,
        invalid_item_at: tuple[str, int] | None = None,
        bad_json_at: tuple[str, int] | None = None,
        fail_at: tuple[str, int] | None = None,
        non_string_at: tuple[str, int] | None = None,
        malformed_run_at: tuple[str, int] | None = None,
        bad_provenance_stage: str | None = None,
        route_unrelated_through_b: bool = False,
    ) -> None:
        self.identity = ProviderIdentity(
            provider="v8-hierarchical-teacher",
            model="fixture-teacher",
            model_digest="8" * 64,
            runtime="pytest",
        )
        self.thinking = False
        self.last_run: CompletionRun | None = None
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []
        self.counts: dict[str, int] = {}
        self.invalid_item_at = invalid_item_at
        self.bad_json_at = bad_json_at
        self.fail_at = fail_at
        self.non_string_at = non_string_at
        self.malformed_run_at = malformed_run_at
        self.bad_provenance_stage = bad_provenance_stage
        self.route_unrelated_through_b = route_unrelated_through_b
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

    def _stage(self, operation: str) -> str:
        return next(
            stage
            for stage, expected_operation in judge_v8._STAGE_OPERATIONS.items()
            if operation == expected_operation
        )

    def _label(self, pair) -> str:
        left = self.fixture_by_text[(pair["left"]["topic"], pair["left"]["content"])]
        right = self.fixture_by_text[(pair["right"]["topic"], pair["right"]["content"])]
        counterparts, label = self.expected[left]
        return label if right in counterparts else "UNRELATED"

    def _choice(self, stage: str, label: str) -> str:
        if stage == judge_v8.STAGE_A:
            if label == "UNRELATED" and not self.route_unrelated_through_b:
                return "TOPIC_ONLY_DIFFERENT_UNIT"
            return "CANDIDATE_RELATIONSHIP_UNIT"
        if stage == judge_v8.STAGE_B:
            if label == "UNRELATED":
                return "NOT_ONE_UNIT"
            if label in ("NEAR_DUPLICATE", "SAME_PRINCIPLE", "CONTEXT_VARIANT"):
                return "CLAIM_OR_GOVERNING_RULE"
            return "PRIMARY_DECISION_OR_JOINT_REVIEW_UNIT"
        if stage == judge_v8.STAGE_C_CLAIM:
            return {
                "NEAR_DUPLICATE": "MATERIALLY_SAME_CLAIM",
                "SAME_PRINCIPLE": "SAME_RULE_SAME_CONTEXT",
                "CONTEXT_VARIANT": "SAME_RULE_MATERIAL_CONTEXT_DIFFERENCE",
            }.get(label, "NOT_SUPPORTED")
        return {
            "CONTEXT_VARIANT": "ALIGNED_MATERIAL_CONTEXT_DIFFERENCE",
            "CONFLICT": "INCOMPATIBLE_SAME_CONTEXT",
            "COMPLEMENT_OR_JOINT_PART": "COMPLEMENTARY_WHOLE_PART_OR_JOINT",
        }.get(label, "NOT_SUPPORTED")

    def complete(self, prompt, *, operation, output_schema=None):
        stage = self._stage(operation)
        index = self.counts.get(stage, 0)
        self.counts[stage] = index + 1
        self.calls.append((prompt, operation, output_schema))
        if self.fail_at == (stage, index):
            raise TimeoutError("private provider endpoint")
        if self.non_string_at == (stage, index):
            response = {"not": "a string"}
        elif self.bad_json_at == (stage, index):
            response = "{not-json"
        else:
            payload = json.loads(prompt.split(judge_v8._PAYLOAD_MARKER, 1)[1])
            decisions = [
                {
                    "pair_id": pair["pair_id"],
                    "choice": self._choice(stage, self._label(pair)),
                }
                for pair in payload["pairs"]
            ]
            if self.invalid_item_at == (stage, index):
                decisions[0]["choice"] = "NOT_A_REAL_CHOICE"
            response = json.dumps({"decisions": decisions})
        retained_identity = (
            replace(self.identity, model="wrong-fixture-teacher")
            if self.bad_provenance_stage == stage
            else self.identity
        )
        retained_response = (
            response if isinstance(response, str) else json.dumps(response)
        )
        self.last_run = CompletionRun(
            identity=retained_identity,
            operation=operation,
            prompt_tokens=(
                -1 if self.malformed_run_at == (stage, index) else len(prompt.split())
            ),
            completion_tokens=len(retained_response.split()),
        )
        return response


@pytest.fixture(scope="module")
def parent_records(tmp_path_factory):
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=26
    )
    ledger_dir = tmp_path_factory.mktemp("task2-judge-v8-parents")
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


@pytest.fixture(scope="module")
def clean_record(parent_records, tmp_path_factory):
    value, records = parent_records
    return judge_v8.run_task2_judge_replay_v8_campaign(
        HierarchicalTeacher(value),  # type: ignore[arg-type]
        parent_ledgers=records,
        ledger_dir=tmp_path_factory.mktemp("task2-judge-v8-clean"),
        provider_connection_seconds=0.25,
    )


def test_v8_reuses_v7_canonical_input_and_gold_independent_stage_a(parent_records):
    _value, records = parent_records
    v7_input = judge_v7.build_task2_judge_replay_v7_input(records)
    v8_input = judge_v8.build_task2_judge_replay_v8_input(records)
    assert v8_input.v7_input == v7_input
    assert v8_input.v7_input.canonical_pairs == v7_input.canonical_pairs
    assert judge_v8.task2_judge_replay_v8_stage_a_call_count(v8_input) == math.ceil(
        len(v7_input.canonical_pairs) / 24
    )

    poisoned_v5 = replace(
        v7_input.v5_input,
        gold_relations_digest="f" * 64,
        replay_freeze_digest="e" * 64,
        parent_ledgers=tuple(reversed(v7_input.v5_input.parent_ledgers)),
    )
    poisoned_v7 = replace(v7_input, v5_input=poisoned_v5)
    assert judge_v8._stage_a_schedule_digest(poisoned_v7) == (
        v8_input.stage_a_schedule_digest
    )


def test_each_prompt_and_schema_exposes_one_stage_enum_and_no_final_label():
    local = [
        {
            "pair_id": "p01",
            "left": {"topic": "t", "content": "a"},
            "right": {"topic": "t", "content": "b"},
        }
    ]
    for stage, choices in judge_v8._STAGE_CHOICES.items():
        prompt = judge_v8._prompt(stage, local)
        schema = judge_v8._schema(stage, ("p01",))
        assert all(label not in prompt for label in judge_v5.TASK2_JUDGE_LABELS)
        encoded_schema = json.dumps(schema)
        assert all(label not in encoded_schema for label in judge_v5.TASK2_JUDGE_LABELS)
        assert schema["properties"]["decisions"]["items"]["properties"]["choice"][
            "enum"
        ] == list(choices)
        assert "label" not in encoded_schema


def test_exact_teacher_routes_branches_projects_once_and_scores(parent_records):
    value, records = parent_records
    replay_input = judge_v8.build_task2_judge_replay_v8_input(records)
    provider = HierarchicalTeacher(value)
    run = judge_v8.judge_task2_candidate_union_v8(
        provider,
        replay_input,  # type: ignore[arg-type]
    )
    assert run.contract_valid
    assert len(run.stage_a_results) == len(replay_input.v7_input.canonical_pairs)
    assert len(run.stage_b_results) == len(run.stage_b_schedule.mappings)
    assert len(run.stage_c_claim_results) == len(run.stage_c_claim_schedule.mappings)
    assert len(run.stage_c_primary_results) == len(
        run.stage_c_primary_schedule.mappings
    )
    assert run.stage_c_claim_results and run.stage_c_primary_results
    assert all(call.pair_count <= 24 for call in run.stage_a_calls)
    assert all(call.pair_count <= 24 for call in run.stage_b_calls)
    assert run.provider_call_count == run.expected_provider_call_count
    assert len(run.outcomes) == len(replay_input.v7_input.canonical_pairs)
    assert len(run.projected_decisions) == len(
        replay_input.v7_input.v5_input.candidate_pairs
    )
    assert run.score["canonical_judge"]["binary_same_hypergroup"]["accuracy"] == 1.0
    assert run.score["canonical_judge"]["group_induced_enum"]["exact_accuracy"] == 1.0
    assert run.score["direction_invariance"]["invariance_rate"] == 1.0
    assert run.score["staged_pipeline"]["outcome_counts"] == {
        "FINAL": len(run.outcomes),
        "ABSTAIN": 0,
        "INVALID_EVIDENCE": 0,
        "MISSING_DUE_CALL": 0,
    }
    assert run.score["scale_readiness_gate"]["measurement_passed"] is True
    assert run.score["scale_readiness_gate"]["scale_promotion_eligible"] is False


def test_item_invalid_retains_valid_peers_and_continues_dynamic_stages(parent_records):
    value, records = parent_records
    replay_input = judge_v8.build_task2_judge_replay_v8_input(records)
    provider = HierarchicalTeacher(value, invalid_item_at=(judge_v8.STAGE_A, 0))
    with pytest.raises(judge_v8.Task2JudgeReplayV8ResponseError) as caught:
        judge_v8.judge_task2_candidate_union_v8(
            provider,
            replay_input,  # type: ignore[arg-type]
        )
    run = caught.value.run
    first = run.stage_a_calls[0]
    assert first.response_envelope_valid is True
    assert first.response_contract_valid is False
    assert sum(item.status == "INVALID_EVIDENCE" for item in first.results) == 1
    assert sum(item.status == "VALID" for item in first.results) == first.pair_count - 1
    assert len(run.stage_a_calls) == math.ceil(len(run.stage_a_results) / 24)
    assert run.stage_b_calls
    assert run.provider_call_count == run.expected_provider_call_count
    assert run.score["staged_pipeline"]["outcome_counts"]["INVALID_EVIDENCE"] == 1
    assert run.score["staged_pipeline"]["outcome_counts"]["MISSING_DUE_CALL"] == 0


def test_parseable_mixed_batch_attributes_duplicate_unknown_and_missing_items(
    parent_records,
):
    _value, records = parent_records
    replay_input = judge_v8.build_task2_judge_replay_v8_input(records)
    mappings = replay_input.v7_input.canonical_to_directed[:3]
    by_id = {f"p{index:02d}": mapping for index, mapping in enumerate(mappings, 1)}
    response = json.dumps(
        {
            "decisions": [
                {"pair_id": "p01", "choice": "CANDIDATE_RELATIONSHIP_UNIT"},
                {"pair_id": "p02", "choice": "TOPIC_ONLY_DIFFERENT_UNIT"},
                {"pair_id": "p02", "choice": "TOPIC_ONLY_DIFFERENT_UNIT"},
                {"pair_id": "p99", "choice": "TOPIC_ONLY_DIFFERENT_UNIT"},
            ]
        }
    )
    results, envelope, valid, category, _error, diagnostics = judge_v8._parse_response(
        stage=judge_v8.STAGE_A,
        raw_response=response,
        provider_error_type=None,
        pair_by_local_id=by_id,
    )
    assert envelope is True
    assert valid is False
    assert category == "INVALID_OUTPUT"
    assert [item.status for item in results] == [
        "VALID",
        "INVALID_EVIDENCE",
        "MISSING_DUE_CALL",
    ]
    assert diagnostics == {
        "attributable_invalid_item_count": 2,
        "invalid_pair_count": 1,
        "unattributable_item_count": 1,
        "missing_pair_count": 1,
        "response_count_mismatch": True,
        "provenance_valid": None,
        "provenance_failure": None,
    }


def test_bad_json_call_marks_only_its_batch_missing_and_schedule_continues(
    parent_records,
):
    value, records = parent_records
    replay_input = judge_v8.build_task2_judge_replay_v8_input(records)
    provider = HierarchicalTeacher(value, bad_json_at=(judge_v8.STAGE_A, 0))
    with pytest.raises(judge_v8.Task2JudgeReplayV8ResponseError) as caught:
        judge_v8.judge_task2_candidate_union_v8(
            provider,
            replay_input,  # type: ignore[arg-type]
        )
    run = caught.value.run
    first = run.stage_a_calls[0]
    assert first.response_envelope_valid is False
    assert all(item.status == "MISSING_DUE_CALL" for item in first.results)
    assert len(run.stage_a_calls) > 1
    assert all(call.response_contract_valid for call in run.stage_a_calls[1:])
    assert run.stage_b_calls
    assert run.score["staged_pipeline"]["outcome_counts"]["MISSING_DUE_CALL"] == 24
    assert run.score["scale_readiness_gate"]["missing_due_call"] == 24


def test_campaign_records_stage_calls_schedules_timing_and_boundary(clean_record):
    record = clean_record
    assert record["contract_valid"] is True
    assert record["durability"]["mode"] == "FINAL_ONLY"
    assert record["staged_protocol"]["provider_returns_final_enum"] is False
    assert record["evaluation_boundary"]["role"] == "JUDGE_ABLATION_ONLY"
    assert record["evaluation_boundary"]["scale_promotion_eligible"] is False
    assert record["calls"]["stage_a"]
    assert record["calls"]["stage_b"]
    assert record["calls"]["stage_c_claim"]
    assert record["calls"]["stage_c_primary"]
    assert (
        record["stage_schedules"]["stage_b"]["prior_output_digest"]
        == (record["stage_schedules"]["stage_a"]["output_digest"])
    )
    assert record["timing"]["provider_connection_seconds"] == 0.25
    assert record["timing"]["total_seconds"] >= 0.25
    validation = judge_v8.validate_task2_judge_replay_v8_record(record)
    assert validation["integrity_valid"] is True
    assert validation["contract_valid"] is True


def test_validator_accepts_honest_invalid_ledgers_and_separates_contract_quality(
    parent_records, tmp_path
):
    value, records = parent_records

    def run(provider, *, known_error_types=()):
        record = judge_v8.run_task2_judge_replay_v8_campaign(
            provider,  # type: ignore[arg-type]
            parent_ledgers=records,
            ledger_dir=tmp_path,
            provider_connection_seconds=0.0,
            known_error_types=known_error_types,
        )
        validation = judge_v8.validate_task2_judge_replay_v8_record(record)
        assert validation["integrity_valid"] is True
        assert validation["contract_valid"] is False
        return record

    item_invalid = run(
        HierarchicalTeacher(value, invalid_item_at=(judge_v8.STAGE_A, 0))
    )
    first_item_call = item_invalid["calls"]["stage_a"][0]
    assert item_invalid["status"] == "INVALID_OUTPUT"
    assert first_item_call["attributable_invalid_item_count"] == 1
    assert first_item_call["invalid_pair_count"] == 1
    assert first_item_call["missing_pair_count"] == 0

    malformed = run(HierarchicalTeacher(value, bad_json_at=(judge_v8.STAGE_A, 0)))
    first_malformed_call = malformed["calls"]["stage_a"][0]
    assert first_malformed_call["response_envelope_valid"] is False
    assert first_malformed_call["missing_pair_count"] == 24

    provider_error = run(
        HierarchicalTeacher(value, fail_at=(judge_v8.STAGE_A, 0)),
        known_error_types=(TimeoutError,),
    )
    failed_call = provider_error["calls"]["stage_a"][0]
    assert provider_error["status"] == "PROVIDER_ERROR"
    assert failed_call["raw_response"] is None
    assert failed_call["provider_run"] is None

    no_response = run(
        HierarchicalTeacher(
            value,
            non_string_at=(judge_v8.STAGE_A, 0),
            bad_provenance_stage=judge_v8.STAGE_A,
        )
    )
    no_response_call = no_response["calls"]["stage_a"][0]
    assert no_response_call["raw_response"] is None
    assert no_response_call["provider_run"] is not None
    assert no_response_call["provenance_valid"] is False
    tampered_no_response = deepcopy(no_response)
    tampered_no_response["calls"]["stage_a"][0]["provider_run"]["operation"] = (
        "wrong operation"
    )
    with pytest.raises(judge_v8.Task2JudgeReplayV8Error):
        judge_v8.validate_task2_judge_replay_v8_record(tampered_no_response)

    malformed_run = run(
        HierarchicalTeacher(value, malformed_run_at=(judge_v8.STAGE_A, 0))
    )
    malformed_run_call = malformed_run["calls"]["stage_a"][0]
    assert malformed_run_call["provider_run"] is None
    assert malformed_run_call["provider_run_digest"] is None
    assert malformed_run_call["provenance_valid"] is False

    provenance_failure = run(
        HierarchicalTeacher(
            value,
            bad_provenance_stage=judge_v8.STAGE_C_PRIMARY,
        )
    )
    primary_calls = provenance_failure["calls"]["stage_c_primary"]
    assert primary_calls
    assert primary_calls[-1]["provenance_valid"] is False
    assert provenance_failure["provider_run"] == primary_calls[-1]["provider_run"]

    tampered_provider_error = deepcopy(provider_error)
    tampered_provider_error["calls"]["stage_a"][0]["raw_response"] = {}
    with pytest.raises(judge_v8.Task2JudgeReplayV8Error):
        judge_v8.validate_task2_judge_replay_v8_record(tampered_provider_error)


def test_validator_rejects_raw_schedule_score_status_shape_and_timing_tampering(
    clean_record,
):
    mutations = []

    def mutate_raw(record):
        record["calls"]["stage_a"][0]["raw_response"] = 7

    mutations.append(mutate_raw)

    def mutate_schedule(record):
        record["stage_schedules"]["stage_b"]["freeze_digest"] = "0" * 64

    mutations.append(mutate_schedule)

    def mutate_score(record):
        record["score"]["staged_pipeline"]["outcome_counts"]["FINAL"] += 1

    mutations.append(mutate_score)

    def mutate_status(record):
        record["status"] = "PROVIDER_ERROR"

    mutations.append(mutate_status)

    def mutate_extra_call_field(record):
        record["calls"]["stage_a"][0]["ignored"] = "tamper"

    mutations.append(mutate_extra_call_field)

    def mutate_bool_as_int(record):
        record["calls"]["stage_a"][0]["call_index"] = True

    mutations.append(mutate_bool_as_int)

    def mutate_top_provider_run(record):
        record["provider_run"]["operation"] = "wrong operation"

    mutations.append(mutate_top_provider_run)

    def mutate_stage_timing(record):
        assert sum(call["elapsed_seconds"] for call in record["calls"]["stage_a"]) > 0
        record["timing"]["stage_a_seconds"] = 0.0

    mutations.append(mutate_stage_timing)

    def mutate_pipeline_timing(record):
        record["timing"]["pipeline_seconds"] = 0.0

    mutations.append(mutate_pipeline_timing)

    def mutate_campaign_timing(record):
        record["timing"]["campaign_seconds"] = 0.0
        record["timing"]["total_seconds"] = record["timing"][
            "provider_connection_seconds"
        ]

    mutations.append(mutate_campaign_timing)

    for mutate in mutations:
        tampered = deepcopy(clean_record)
        mutate(tampered)
        with pytest.raises(judge_v8.Task2JudgeReplayV8Error):
            judge_v8.validate_task2_judge_replay_v8_record(tampered)


def test_comparator_exposes_stage_disagreement_even_when_final_projection_matches(
    parent_records, tmp_path
):
    value, records = parent_records
    exact = judge_v8.run_task2_judge_replay_v8_campaign(
        HierarchicalTeacher(value),  # type: ignore[arg-type]
        parent_ledgers=records,
        ledger_dir=tmp_path,
        provider_connection_seconds=0.0,
    )
    rerouted = judge_v8.run_task2_judge_replay_v8_campaign(
        HierarchicalTeacher(  # type: ignore[arg-type]
            value, route_unrelated_through_b=True
        ),
        parent_ledgers=records,
        ledger_dir=tmp_path,
        provider_connection_seconds=0.0,
    )
    comparison = judge_v8.compare_task2_judge_replay_v8_records(exact, rerouted)
    total = comparison["canonical_pair_count"]
    assert comparison["stage_agreement"][judge_v8.STAGE_A]["exact"] < total
    assert comparison["dynamic_freezes_identical"][judge_v8.STAGE_B] is False
    assert comparison["final_projection_agreement"] == {
        "exact": total,
        "total": total,
        "exact_accuracy": 1.0,
    }
    assert (
        comparison["binary_accept_reject_sentinel_agreement"]["exact_accuracy"] == 1.0
    )
    assert comparison["source_accepted_set_agreement"]["exact_accuracy"] == 1.0
    assert comparison["parity_gate"]["passed"] is False

    with pytest.raises(judge_v8.Task2JudgeReplayV8Error):
        judge_v8.compare_task2_judge_replay_v8_records(exact, exact)
