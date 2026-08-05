"""Contracts for the fixed-candidate Task 2 judge replay v5 harness."""
from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path

import pytest

import memcommit.eval.task2_judge_replay_v5 as judge_v5
import memcommit.eval.task2_retrieval_v4 as retrieval_v4
from memcommit.eval.task2_discovery import (
    build_task2_discovery_input,
    load_task2_discovery_corpus,
)
from memcommit.eval.task2_judge_replay_v5 import (
    TASK2_GROUP_INDUCED_GOLD_BOUNDARY,
    TASK2_JUDGE_REPLAY_V5_BATCH_SIZE,
    TASK2_JUDGE_REPLAY_V5_DURABILITY,
    Task2JudgeReplayV5Error,
    Task2JudgeReplayV5ResponseError,
    build_task2_judge_replay_v5_input,
    compare_task2_judge_replay_v5_records,
    judge_task2_candidate_union_v5,
    run_task2_judge_replay_v5_campaign,
    task2_judge_replay_v5_provider_call_count,
)
from memcommit.eval.task2_retrieval_v4 import (
    CANDIDATE_STAGE,
    LEFT_TO_RIGHT,
    VERIFIER_STAGE,
    run_task2_retrieval_v4_campaign,
)
from memcommit.provider_types import CompletionRun, ProviderIdentity


class V4ParentTeacher:
    """Create strict V4 parents with different Gold-blind filler candidates."""

    def __init__(self, value, *, reverse_fillers: bool) -> None:
        name = "parent-reverse" if reverse_fillers else "parent-forward"
        self.identity = ProviderIdentity(
            provider=name,
            model="fixture-teacher",
            model_digest=("b" if reverse_fillers else "a") * 64,
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


class JudgeTeacher:
    """Resolve fixture text while seeing only call-local pair IDs."""

    def __init__(self, value, *, mutations=None) -> None:
        self.identity = ProviderIdentity(
            provider="judge-teacher",
            model="fixture-teacher",
            model_digest="c" * 64,
            runtime="pytest",
        )
        self.thinking = "off"
        self.last_run: CompletionRun | None = None
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []
        self.mutations = dict(mutations or {})
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

    def _answer(self, prompt: str) -> str:
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
        return json.dumps({"judgments": judgments})

    def complete(self, prompt, *, operation, output_schema=None):
        call_index = len(self.calls)
        self.calls.append((prompt, operation, output_schema))
        mutation = self.mutations.get(call_index)
        if isinstance(mutation, BaseException):
            raise mutation
        response = self._answer(prompt)
        if mutation is not None:
            decoded = json.loads(response)
            mutation(decoded)
            response = json.dumps(decoded)
        self.last_run = CompletionRun(
            identity=self.identity,
            operation=operation,
            prompt_tokens=len(prompt.split()),
            completion_tokens=len(response.split()),
        )
        return response


@pytest.fixture
def parent_records(tmp_path):
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=26
    )
    records = []
    for reverse in (False, True):
        records.append(
            run_task2_retrieval_v4_campaign(
                V4ParentTeacher(value, reverse_fillers=reverse),  # type: ignore[arg-type]
                ledger_dir=tmp_path,
                provider_connection_seconds=0.0,
                group_count=26,
            )
        )
    return value, records


def _parent_candidate_pairs(record):
    return {
        (
            selection["direction"],
            selection["source_fixture_id"],
            target,
        )
        for selection in record["candidate_selections"]
        for target in selection["target_fixture_ids"]
    }


def test_candidate_union_is_full_deterministic_gold_blind_and_accepts_paths(
    parent_records,
):
    value, records = parent_records
    forward = build_task2_judge_replay_v5_input(records)
    reverse = build_task2_judge_replay_v5_input(list(reversed(records)))
    paths = build_task2_judge_replay_v5_input(
        [Path(record["ledger_path"]) for record in reversed(records)]
    )

    union = {
        (pair.direction, pair.source_fixture_id, pair.target_fixture_id)
        for pair in forward.candidate_pairs
    }
    assert len(union) > (len(value.left_items) + len(value.right_items)) * 3
    assert union == _parent_candidate_pairs(records[0]) | _parent_candidate_pairs(
        records[1]
    )
    assert forward.candidate_pairs == reverse.candidate_pairs == paths.candidate_pairs
    assert forward.candidate_bundle_digest == reverse.candidate_bundle_digest
    assert forward.replay_freeze_digest == reverse.replay_freeze_digest
    assert [item.ledger_digest for item in forward.parent_ledgers] == sorted(
        item.ledger_digest for item in forward.parent_ledgers
    )

    # The pure union step never reads reviewed groups. Strict validation and
    # frozen-rung reconstruction happen around it, not inside its construction.
    gold_poisoned = copy.deepcopy(records)
    for record in gold_poisoned:
        record["expected_groups"] = object()
    assert judge_v5._gold_blind_candidate_union(
        gold_poisoned, input_digest=forward.input_digest
    ) == forward.candidate_pairs
    lexical = tuple(
        sorted(
            forward.candidate_pairs,
            key=lambda pair: (
                pair.direction,
                pair.source_fixture_id,
                pair.target_fixture_id,
            ),
        )
    )
    assert forward.candidate_pairs != lexical

    first_provider = JudgeTeacher(value)
    second_provider = JudgeTeacher(value)
    judge_task2_candidate_union_v5(first_provider, forward)  # type: ignore[arg-type]
    judge_task2_candidate_union_v5(second_provider, reverse)  # type: ignore[arg-type]
    assert [call[0] for call in first_provider.calls] == [
        call[0] for call in second_provider.calls
    ]


def test_exact_teacher_judges_full_union_in_fixed_local_pair_batches(parent_records):
    value, records = parent_records
    replay = build_task2_judge_replay_v5_input(records)
    provider = JudgeTeacher(value)

    run = judge_task2_candidate_union_v5(provider, replay)  # type: ignore[arg-type]

    assert run.contract_valid is True
    assert len(run.decisions) == len(replay.candidate_pairs)
    assert run.provider_call_count == task2_judge_replay_v5_provider_call_count(replay)
    assert run.provider_call_count == math.ceil(
        len(replay.candidate_pairs) / TASK2_JUDGE_REPLAY_V5_BATCH_SIZE
    )
    assert all(call.pair_count <= TASK2_JUDGE_REPLAY_V5_BATCH_SIZE for call in run.calls)
    assert run.score["binary_same_hypergroup"]["accuracy"] == 1.0
    assert run.score["multi_member_binary"]["recall"] == 1.0
    assert run.score["multi_member_binary"]["precision"] == 1.0
    assert run.score["group_induced_enum"]["exact_accuracy"] == 1.0
    assert run.score["group_induced_enum"]["boundary"] == (
        TASK2_GROUP_INDUCED_GOLD_BOUNDARY
    )
    assert run.score["source_accepted_set"]["exact_accuracy"] == 1.0
    assert run.score["reviewed_one_to_one_source_set"]["exact"] == 48
    assert run.score["reviewed_one_to_one_source_set"]["total"] == 48
    assert run.score["candidate_ceiling"]["recoverable_sources"] == 56
    assert run.score["candidate_ceiling"]["recoverable_groups"] == 26
    assert all(call.raw_response for call in run.calls)
    assert all(call.elapsed_seconds >= 0 for call in run.calls)
    assert run.elapsed_seconds >= sum(call.elapsed_seconds for call in run.calls)
    assert all(
        call.response_digest == hashlib.sha256(call.raw_response.encode()).hexdigest()
        for call in run.calls
        if call.raw_response is not None
    )

    fixture_ids = set(replay.task2_input.alias_to_fixture_id.values())
    for prompt, _operation, schema in provider.calls:
        payload = json.loads(prompt.split(judge_v5._PAYLOAD_MARKER, 1)[1])
        assert [item["pair_id"] for item in payload["pairs"]] == [
            f"p{index:02d}" for index in range(1, len(payload["pairs"]) + 1)
        ]
        assert not any(fixture_id in prompt for fixture_id in fixture_ids)
        assert schema["properties"]["judgments"]["minItems"] == len(
            payload["pairs"]
        )
        assert "uniqueItems" not in schema["properties"]["judgments"]


@pytest.mark.parametrize(
    "mutation,expected_message",
    [
        (
            lambda value: value["judgments"][0].__setitem__("pair_id", "p99"),
            "invalid call-local pair_id",
        ),
        (
            lambda value: value["judgments"][1].__setitem__(
                "pair_id", value["judgments"][0]["pair_id"]
            ),
            "every call-local pair_id exactly once",
        ),
        (
            lambda value: value["judgments"].pop(),
            "every call-local pair_id exactly once",
        ),
    ],
)
def test_invalid_pair_id_contract_is_retained_and_fixed_calls_continue(
    parent_records, mutation, expected_message
):
    value, records = parent_records
    replay = build_task2_judge_replay_v5_input(records)
    provider = JudgeTeacher(value, mutations={0: mutation})

    with pytest.raises(Task2JudgeReplayV5ResponseError) as captured:
        judge_task2_candidate_union_v5(provider, replay)  # type: ignore[arg-type]

    run = captured.value.run
    assert expected_message in str(captured.value)
    assert len(provider.calls) == run.provider_call_count == (
        run.expected_provider_call_count
    )
    assert run.calls[0].response_contract_valid is False
    assert run.calls[0].raw_response is not None
    assert all(call.response_contract_valid for call in run.calls[1:])
    assert len(run.decisions) == len(replay.candidate_pairs) - run.calls[0].pair_count
    missing = run.score["binary_same_hypergroup"]
    assert missing["missing_positive"] + missing["missing_negative"] == (
        run.calls[0].pair_count
    )


def test_known_provider_error_continues_and_campaign_retains_frozen_identity(
    parent_records, tmp_path
):
    value, records = parent_records
    replay = build_task2_judge_replay_v5_input(records)
    provider = JudgeTeacher(value, mutations={1: TimeoutError("private endpoint")})

    record = run_task2_judge_replay_v5_campaign(
        provider,  # type: ignore[arg-type]
        parent_ledgers=records,
        ledger_dir=tmp_path,
        provider_connection_seconds=0.25,
        known_error_types=(TimeoutError,),
    )

    assert record["status"] == "PROVIDER_ERROR"
    assert record["contract_valid"] is False
    assert record["durability"]["mode"] == TASK2_JUDGE_REPLAY_V5_DURABILITY
    assert record["provider_call_count"] == (
        task2_judge_replay_v5_provider_call_count(replay)
    )
    assert len(provider.calls) == task2_judge_replay_v5_provider_call_count(replay)
    assert record["calls"][1]["failure_category"] == "PROVIDER"
    assert record["calls"][1]["error_type"] == "TimeoutError"
    assert "private endpoint" not in json.dumps(record)
    assert record["candidate_bundle"]["digest"] == replay.candidate_bundle_digest
    assert record["candidate_bundle"]["replay_freeze_digest"] == (
        replay.replay_freeze_digest
    )
    assert [item["ledger_digest"] for item in record["parents"]] == [
        item.ledger_digest for item in replay.parent_ledgers
    ]
    assert Path(record["ledger_path"]).exists()
    assert record["calibration_boundary"] == {
        "parent_corpus_role": "CONSUMED_CALIBRATION",
        "reviewed_relations_used_to_validate_and_build_frozen_input": True,
        "candidate_union_construction_uses_reviewed_relations": False,
        "provider_call_branching_after_replay_input_build_uses_reviewed_relations": False,
        "reviewed_relations_reused_for_scoring_after_all_provider_calls": True,
        "independent_holdout": False,
    }


def test_non_string_provider_response_is_invalid_and_schedule_continues(
    parent_records,
):
    value, records = parent_records
    replay = build_task2_judge_replay_v5_input(records)

    class NonStringFirstJudge(JudgeTeacher):
        def complete(self, prompt, *, operation, output_schema=None):
            if not self.calls:
                self.calls.append((prompt, operation, output_schema))
                return {"judgments": []}
            return super().complete(
                prompt, operation=operation, output_schema=output_schema
            )

    provider = NonStringFirstJudge(value)
    with pytest.raises(Task2JudgeReplayV5ResponseError) as captured:
        judge_task2_candidate_union_v5(provider, replay)  # type: ignore[arg-type]

    run = captured.value.run
    assert run.calls[0].failure_category == "INVALID_OUTPUT"
    assert run.calls[0].raw_response is None
    assert len(provider.calls) == run.expected_provider_call_count
    assert all(call.response_contract_valid for call in run.calls[1:])


def test_parent_contract_and_fixed_batch_size_fail_closed(parent_records):
    _value, records = parent_records
    invalid = copy.deepcopy(records[0])
    invalid["contract_valid"] = False

    with pytest.raises(Task2JudgeReplayV5Error, match="contract-valid"):
        build_task2_judge_replay_v5_input([invalid, records[1]])
    with pytest.raises(Task2JudgeReplayV5Error, match="at least two"):
        build_task2_judge_replay_v5_input([records[0]])
    replay = build_task2_judge_replay_v5_input(records)
    with pytest.raises(Task2JudgeReplayV5Error, match="frozen at 24"):
        task2_judge_replay_v5_provider_call_count(replay, batch_size=12)


def test_local_lock_rejects_coherently_rewritten_parent_reviewed_groups(
    parent_records,
):
    _value, records = parent_records
    rewritten = copy.deepcopy(records)
    for record in rewritten:
        first = list(record["expected_groups"][0]["right_fixture_ids"])
        second = list(record["expected_groups"][1]["right_fixture_ids"])
        first[0], second[0] = second[0], first[0]
        record["expected_groups"][0]["right_fixture_ids"] = tuple(first)
        record["expected_groups"][1]["right_fixture_ids"] = tuple(second)

    with pytest.raises(Task2JudgeReplayV5Error, match="local frozen rung"):
        build_task2_judge_replay_v5_input(rewritten)


def test_raw_stage_a_aliases_must_exactly_reconstruct_normalized_candidates(
    parent_records,
):
    _value, records = parent_records
    rewritten = copy.deepcopy(records)
    record = rewritten[0]
    nested = record["calls"][0]["selections"][0]
    current = set(nested["target_fixture_ids"])
    all_right = {
        target
        for group in record["expected_groups"]
        for target in group["right_fixture_ids"]
    }
    replacement = next(target for target in sorted(all_right) if target not in current)
    nested_targets = list(nested["target_fixture_ids"])
    nested_targets[0] = replacement
    nested["target_fixture_ids"] = tuple(nested_targets)
    top_level = next(
        selection
        for selection in record["candidate_selections"]
        if selection["direction"] == nested["direction"]
        and selection["source_fixture_id"] == nested["source_fixture_id"]
    )
    top_targets = list(top_level["target_fixture_ids"])
    top_targets[0] = replacement
    top_level["target_fixture_ids"] = tuple(top_targets)

    with pytest.raises(Task2JudgeReplayV5Error, match="raw Stage-A aliases"):
        build_task2_judge_replay_v5_input(rewritten)


def test_parent_uniqueness_uses_run_id_not_mutable_ledger_path(parent_records):
    _value, records = parent_records
    duplicate_run = copy.deepcopy(records[0])
    duplicate_run["ledger_path"] = "/different/storage/copy.json"

    with pytest.raises(Task2JudgeReplayV5Error, match="distinct parent run IDs"):
        build_task2_judge_replay_v5_input([records[0], duplicate_run])

    invalid_identity = copy.deepcopy(records)
    invalid_identity[1]["provider"]["model"] = ""
    with pytest.raises(Task2JudgeReplayV5Error, match="provider identity"):
        build_task2_judge_replay_v5_input(invalid_identity)


def test_direct_replay_input_revalidates_gold_and_candidate_side_membership(
    parent_records,
):
    value, records = parent_records
    replay = build_task2_judge_replay_v5_input(records)
    altered_relations = list(value.expected)
    altered_relations[0], altered_relations[1] = (
        altered_relations[1],
        altered_relations[0],
    )
    altered_task2 = replace(value, expected=tuple(altered_relations))
    altered_replay = replace(replay, task2_input=altered_task2)

    with pytest.raises(Task2JudgeReplayV5Error, match="frozen replay input"):
        judge_task2_candidate_union_v5(
            JudgeTeacher(value), altered_replay  # type: ignore[arg-type]
        )

    first_pair = replay.candidate_pairs[0]
    escaped_pair = replace(
        first_pair,
        source_fixture_id=first_pair.target_fixture_id,
        target_fixture_id=first_pair.source_fixture_id,
    )
    escaped_pairs = (escaped_pair, *replay.candidate_pairs[1:])
    escaped_pairs = judge_v5._order_candidate_pairs(
        escaped_pairs, input_digest=replay.input_digest
    )
    escaped_bundle_digest = hashlib.sha256(
        judge_v5._json(
            judge_v5._candidate_bundle_material(escaped_pairs)
        ).encode()
    ).hexdigest()
    escaped_freeze_digest = hashlib.sha256(
        judge_v5._json(
            {
                "pipeline": judge_v5.TASK2_JUDGE_REPLAY_V5_PIPELINE,
                "corpus_digest": replay.corpus_digest,
                "sidecar_digest": replay.sidecar_digest,
                "gold_relations_digest": replay.gold_relations_digest,
                "input_digest": replay.input_digest,
                "parent_ledger_digests": [
                    item.ledger_digest for item in replay.parent_ledgers
                ],
                "candidate_bundle_digest": escaped_bundle_digest,
                "batch_size": TASK2_JUDGE_REPLAY_V5_BATCH_SIZE,
            }
        ).encode()
    ).hexdigest()
    escaped_replay = replace(
        replay,
        candidate_pairs=escaped_pairs,
        candidate_bundle_digest=escaped_bundle_digest,
        replay_freeze_digest=escaped_freeze_digest,
    )
    with pytest.raises(Task2JudgeReplayV5Error, match="frozen replay input"):
        judge_task2_candidate_union_v5(
            JudgeTeacher(value), escaped_replay  # type: ignore[arg-type]
        )

    duplicate_parent = replace(
        replay.parent_ledgers[1], run_id=replay.parent_ledgers[0].run_id
    )
    duplicate_run_replay = replace(
        replay,
        parent_ledgers=(replay.parent_ledgers[0], duplicate_parent),
    )
    with pytest.raises(Task2JudgeReplayV5Error, match="parent freeze identity"):
        judge_task2_candidate_union_v5(
            JudgeTeacher(value), duplicate_run_replay  # type: ignore[arg-type]
        )


def test_strict_record_comparator_reports_literal_judge_parity_and_tampering(
    parent_records, tmp_path
):
    value, records = parent_records
    first = run_task2_judge_replay_v5_campaign(
        JudgeTeacher(value),  # type: ignore[arg-type]
        parent_ledgers=records,
        ledger_dir=tmp_path,
        provider_connection_seconds=0.0,
    )
    second = run_task2_judge_replay_v5_campaign(
        JudgeTeacher(value),  # type: ignore[arg-type]
        parent_ledgers=records,
        ledger_dir=tmp_path,
        provider_connection_seconds=0.0,
    )

    parity = compare_task2_judge_replay_v5_records(first, second)
    assert parity["fixed_call_inputs_identical"] is True
    assert parity["exact_enum_agreement"]["exact_accuracy"] == 1.0
    assert parity["binary_accept_reject_agreement"]["exact_accuracy"] == 1.0
    assert parity["source_accepted_set_agreement"]["exact_accuracy"] == 1.0
    assert parity["multi_member_agreement"]["pair_enum"]["exact_accuracy"] == 1.0
    assert parity["multi_member_agreement"]["pair_binary_accept_reject"][
        "exact_accuracy"
    ] == 1.0
    assert parity["multi_member_agreement"]["source_accepted_set"][
        "exact_accuracy"
    ] == 1.0
    assert parity["parity_gate"]["passed"] is True
    quadrants = parity["reviewed_one_to_one_direct_enum_quadrants"]
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

    for field in ("prompt_digest", "schema_digest", "local_id_mapping_digest"):
        altered = copy.deepcopy(second)
        altered["calls"][0][field] = "d" * 64
        with pytest.raises(Task2JudgeReplayV5Error, match="call evidence"):
            compare_task2_judge_replay_v5_records(first, altered)

    altered_freeze = copy.deepcopy(second)
    altered_freeze["candidate_bundle"]["replay_freeze_digest"] = "e" * 64
    with pytest.raises(Task2JudgeReplayV5Error, match="replay freeze"):
        compare_task2_judge_replay_v5_records(first, altered_freeze)

    altered_raw = copy.deepcopy(second)
    altered_raw["calls"][0]["raw_response"] += " "
    with pytest.raises(Task2JudgeReplayV5Error, match="call evidence"):
        compare_task2_judge_replay_v5_records(first, altered_raw)

    altered_score = copy.deepcopy(second)
    altered_score["score"]["binary_same_hypergroup"]["accuracy"] = 0.0
    with pytest.raises(Task2JudgeReplayV5Error, match="retained score"):
        compare_task2_judge_replay_v5_records(first, altered_score)


def test_record_comparator_separates_enum_binary_and_source_set_disagreement(
    parent_records, tmp_path
):
    value, records = parent_records
    first = run_task2_judge_replay_v5_campaign(
        JudgeTeacher(value),  # type: ignore[arg-type]
        parent_ledgers=records,
        ledger_dir=tmp_path,
        provider_connection_seconds=0.0,
    )

    def flip_first_label(decoded):
        current = decoded["judgments"][0]["label"]
        decoded["judgments"][0]["label"] = (
            "CONFLICT" if current == "UNRELATED" else "UNRELATED"
        )

    divergent = run_task2_judge_replay_v5_campaign(
        JudgeTeacher(value, mutations={0: flip_first_label}),  # type: ignore[arg-type]
        parent_ledgers=records,
        ledger_dir=tmp_path,
        provider_connection_seconds=0.0,
    )
    parity = compare_task2_judge_replay_v5_records(first, divergent)

    assert parity["exact_enum_agreement"]["exact"] == parity["pair_count"] - 1
    assert parity["binary_accept_reject_agreement"]["exact"] == (
        parity["pair_count"] - 1
    )
    assert parity["source_accepted_set_agreement"]["exact"] == (
        parity["source_accepted_set_agreement"]["total"] - 1
    )
    assert parity["parity_gate"]["passed"] is False
