"""Contracts for the two-stage Task 2 retrieval v4 harness."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re

import pytest

import memcommit.eval.task2_retrieval_v4 as retrieval_v4
from memcommit.eval.task2_discovery import (
    build_task2_discovery_input,
    load_task2_discovery_corpus,
)
from memcommit.eval.task2_retrieval_v4 import (
    CANDIDATE_STAGE,
    LEFT_TO_RIGHT,
    RIGHT_TO_LEFT,
    TASK2_RETRIEVAL_V4_BATCH_SIZE,
    TASK2_RETRIEVAL_V4_DURABILITY,
    TASK2_RETRIEVAL_V4_KIND,
    VERIFIER_STAGE,
    Task2RetrievalV4Error,
    Task2RetrievalV4ResponseError,
    compare_task2_retrieval_v4_records,
    discover_task2_counterparts_v4,
    evaluate_task2_retrieval_v4_rung_gate,
    run_task2_retrieval_v4_campaign,
    task2_retrieval_v4_provider_call_count,
)
from memcommit.provider_types import CompletionRun, ProviderIdentity


class ReviewedFakeProvider:
    """Test teacher that resolves local text, never fixture IDs in the prompt."""

    def __init__(self, value, *, mutations=None) -> None:
        self.identity = ProviderIdentity(
            provider="fake",
            model="reviewed-fixture-teacher",
            model_digest="c" * 64,
            runtime="pytest",
        )
        self.thinking = "off"
        self.last_run: CompletionRun | None = None
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []
        self.mutations = dict(mutations or {})
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
        fixture_by_text = (
            self.left_fixture_by_text if side == "left" else self.right_fixture_by_text
        )
        return fixture_by_text[(item["topic"], item["content"])]

    def _answer(self, prompt: str) -> str:
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
                target_by_fixture = {
                    self._fixture(target, side=target_side): target["id"]
                    for target in targets
                }
                selected = [target_by_fixture[item] for item in sorted(expected)]
                selected.extend(
                    target["id"]
                    for target in targets
                    if target["id"] not in selected
                )
                selections.append(
                    {"source_id": source["id"], "target_ids": selected[:3]}
                )
        else:
            for source in payload["sources"]:
                expected = self.expected[self._fixture(source, side=source_side)]
                selected = [
                    target["id"]
                    for target in source["candidates"]
                    if self._fixture(target, side=target_side) in expected
                ]
                selections.append(
                    {"source_id": source["id"], "target_ids": selected}
                )
        return json.dumps({"selections": selections})

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


def _value(group_count=26):
    return build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=group_count
    )


def test_full_150_by_150_exact_teacher_runs_40_calls_and_scores_300_members():
    value = _value(138)
    provider = ReviewedFakeProvider(value)

    run = discover_task2_counterparts_v4(provider, value)  # type: ignore[arg-type]

    assert len(value.left_items) == len(value.right_items) == 150
    assert len(provider.calls) == run.provider_call_count == 40
    assert run.expected_provider_call_count == (
        math.ceil(150 / TASK2_RETRIEVAL_V4_BATCH_SIZE) * 4
    )
    assert run.contract_valid is True
    assert [call.stage for call in run.calls[:4]] == [
        CANDIDATE_STAGE,
        VERIFIER_STAGE,
        CANDIDATE_STAGE,
        VERIFIER_STAGE,
    ]
    assert [call.direction for call in run.calls[:20]] == [LEFT_TO_RIGHT] * 20
    assert [call.direction for call in run.calls[20:]] == [RIGHT_TO_LEFT] * 20
    assert len(run.candidate_selections) == len(run.final_selections) == 300
    assert run.score["candidate_retrieval"]["recall_at_3"] == 1.0
    final = run.score["final_group_co_membership"]
    assert final["reviewed_one_to_one_subset"]["overall"] == {
        "exact": 258,
        "total": 258,
        "exact_accuracy": 1.0,
        "macro_jaccard": 1.0,
    }
    assert final["all_reviewed_groups"]["overall"] == {
        "exact": 300,
        "total": 300,
        "exact_accuracy": 1.0,
        "macro_jaccard": 1.0,
    }
    assert run.score["grouping_diagnostics"]["reciprocal"]["score"][
        "exact_complete_grouping"
    ] is True
    assert run.score["grouping_diagnostics"]["union"]["score"][
        "exact_complete_grouping"
    ] is True
    assert run.score["grouping_diagnostics"]["reciprocal"]["score"][
        "multi_member_group_recall"
    ] == 1.0
    assert all(call.raw_response for call in run.calls)
    assert all(call.prompt_digest and call.schema_digest for call in run.calls)
    assert all(call.local_id_mapping_digest for call in run.calls)
    assert all(call.elapsed_seconds >= 0.0 for call in run.calls)
    assert all(
        call.response_digest == hashlib.sha256(call.raw_response.encode()).hexdigest()
        for call in run.calls
        if call.raw_response is not None
    )


def test_stage_a_can_include_extras_while_stage_b_recovers_exact_membership():
    value = _value(26)
    provider = ReviewedFakeProvider(value)

    run = discover_task2_counterparts_v4(provider, value)  # type: ignore[arg-type]

    candidate = next(
        selection
        for selection in run.candidate_selections
        if len(provider.expected[selection.source_fixture_id]) == 1
    )
    final = next(
        selection
        for selection in run.final_selections
        if selection.source_fixture_id == candidate.source_fixture_id
        and selection.direction == candidate.direction
    )
    assert len(candidate.target_fixture_ids) == 3
    assert frozenset(candidate.target_fixture_ids) != provider.expected[
        candidate.source_fixture_id
    ]
    assert frozenset(final.target_fixture_ids) == provider.expected[
        final.source_fixture_id
    ]
    assert run.score["candidate_retrieval"]["recall_at_3"] == 1.0
    assert run.score["final_group_co_membership"]["all_reviewed_groups"][
        "overall"
    ]["exact_accuracy"] == 1.0


def test_valid_stage_a_zero_hit_allows_verifier_to_return_empty_selection():
    value = _value(26)
    provider = ReviewedFakeProvider(value)

    def replace_first_candidate_with_three_wrong_targets(decoded):
        prompt = provider.calls[-1][0]
        payload = json.loads(prompt.split(retrieval_v4._PAYLOAD_MARKER, 1)[1])
        source = payload["sources"][0]
        expected = provider.expected[provider._fixture(source, side="left")]
        wrong = [
            target["id"]
            for target in payload["targets"]
            if provider._fixture(target, side="right") not in expected
        ][:3]
        decoded["selections"][0]["target_ids"] = wrong

    provider.mutations[0] = replace_first_candidate_with_three_wrong_targets
    run = discover_task2_counterparts_v4(provider, value)  # type: ignore[arg-type]

    source = run.candidate_selections[0].source_fixture_id
    candidate = next(
        item for item in run.candidate_selections if item.source_fixture_id == source
    )
    final = next(
        item
        for item in run.final_selections
        if item.source_fixture_id == source and item.direction == LEFT_TO_RIGHT
    )
    assert provider.expected[source].isdisjoint(candidate.target_fixture_ids)
    assert final.target_fixture_ids == ()
    assert run.contract_valid is True
    assert run.score["candidate_retrieval"]["recall_at_3"] < 1.0
    assert run.score["final_group_co_membership"]["all_reviewed_groups"][
        "overall"
    ]["exact"] == 55


def test_grouping_score_reports_multi_member_recovery_separately():
    value = _value(26)
    one_to_one_only = tuple(
        retrieval_v4.Task2RetrievalV4Group(
            relation.left_fixture_ids,
            relation.right_fixture_ids,
        )
        for relation in value.expected
        if len(relation.left_fixture_ids) == len(relation.right_fixture_ids) == 1
    )

    score = retrieval_v4._grouping_score(value, one_to_one_only)

    assert score["multi_member_expected_groups"] == 2
    assert score["multi_member_exact_groups"] == 0
    assert score["multi_member_group_recall"] == 0.0
    assert score["exact_groups"] == 24


@pytest.mark.parametrize(
    "mutation,expected_message",
    [
        (
            lambda value: value["selections"][0].__setitem__(
                "source_id", "s99"
            ),
            "invalid call-local source",
        ),
        (
            lambda value: value["selections"][0].__setitem__(
                "target_ids",
                [value["selections"][0]["target_ids"][0]] * 3,
            ),
            "duplicate call-local target_id",
        ),
        (
            lambda value: value["selections"].pop(),
            "every call-local source_id exactly once",
        ),
    ],
)
def test_invalid_candidate_contract_is_retained_and_all_eight_calls_continue(
    mutation, expected_message
):
    value = _value(26)
    provider = ReviewedFakeProvider(value, mutations={0: mutation})

    with pytest.raises(Task2RetrievalV4ResponseError) as captured:
        discover_task2_counterparts_v4(provider, value)  # type: ignore[arg-type]

    run = captured.value.run
    assert expected_message in str(captured.value)
    assert len(provider.calls) == run.provider_call_count == 8
    assert run.expected_provider_call_count == 8
    assert run.calls[0].contract_valid is False
    assert run.calls[0].raw_response is not None
    assert run.calls[1].stage == VERIFIER_STAGE
    assert run.calls[1].response_contract_valid is True
    assert run.calls[1].dependency_valid is False
    assert run.calls[1].contract_valid is False
    assert run.calls[1].failure_category == "DEPENDENCY"
    assert all(call.contract_valid for call in run.calls[2:])
    assert len(run.final_selections) == 56 - len(run.calls[1].source_fixture_ids)


def test_configured_provider_error_continues_schedule_and_campaign_retains_it(
    tmp_path,
):
    class SecretTransportError(RuntimeError):
        pass

    value = _value(26)
    provider = ReviewedFakeProvider(
        value,
        mutations={0: SecretTransportError("secret-token-and-prompt")},
    )

    record = run_task2_retrieval_v4_campaign(
        provider,  # type: ignore[arg-type]
        ledger_dir=tmp_path,
        provider_connection_seconds=0.5,
        group_count=26,
        known_error_types=(SecretTransportError,),
    )

    assert len(provider.calls) == record["provider_call_count"] == 8
    assert record["status"] == "PROVIDER_ERROR"
    assert record["contract_valid"] is False
    failed = record["calls"][0]
    assert failed["failure_category"] == "PROVIDER"
    assert failed["error_type"] == "SecretTransportError"
    assert failed["raw_response"] is None
    assert failed["response_digest"] is None
    paired = record["calls"][1]
    assert paired["stage"] == VERIFIER_STAGE
    assert paired["dependency_valid"] is False
    assert paired["raw_response"] is not None
    assert all(call["contract_valid"] for call in record["calls"][2:])
    persisted = (tmp_path / "task2-retrieval-v4").glob("*.json")
    persisted_text = next(persisted).read_text(encoding="utf-8")
    assert "secret-token-and-prompt" not in persisted_text
    assert "SecretTransportError" in persisted_text


def test_prompts_and_schemas_expose_only_call_local_ids():
    value = _value(26)
    provider = ReviewedFakeProvider(value)

    run = discover_task2_counterparts_v4(provider, value)  # type: ignore[arg-type]

    opaque_aliases = set(value.alias_to_fixture_id)
    fixture_ids = set(value.alias_to_fixture_id.values())
    for prompt, _operation, schema in provider.calls:
        schema_text = json.dumps(schema)
        assert "uniqueItems" not in schema_text
        assert all(alias not in prompt and alias not in schema_text for alias in opaque_aliases)
        assert all(
            fixture_id not in prompt and fixture_id not in schema_text
            for fixture_id in fixture_ids
        )
        payload = json.loads(prompt.split(retrieval_v4._PAYLOAD_MARKER, 1)[1])
        assert all(re.fullmatch(r"s\d{2}", item["id"]) for item in payload["sources"])
        if payload["stage"] == CANDIDATE_STAGE:
            assert all(
                re.fullmatch(r"t\d{3}", item["id"]) for item in payload["targets"]
            )
        else:
            assert all(
                re.fullmatch(r"t\d{3}", target["id"])
                for source in payload["sources"]
                for target in source["candidates"]
            )
    assert all(re.fullmatch(r"[0-9a-f]{64}", call.local_id_mapping_digest) for call in run.calls)


def test_valid_frozen_campaign_records_lock_rung_uuid_and_final_only_durability(
    tmp_path,
):
    value = _value(26)
    provider = ReviewedFakeProvider(value)

    record = run_task2_retrieval_v4_campaign(
        provider,  # type: ignore[arg-type]
        ledger_dir=tmp_path,
        provider_connection_seconds=1.25,
        group_count=26,
    )

    assert record["kind"] == TASK2_RETRIEVAL_V4_KIND
    assert re.fullmatch(r"\d{8}T\d{12}Z-[0-9a-f]{32}", record["run_id"])
    assert record["status"] == "VALID"
    assert record["contract_valid"] is True
    assert record["provider_call_count"] == record["expected_provider_call_count"] == 8
    assert record["lock"]["corpus_locked"] is True
    assert record["lock"]["rung_locked"] is True
    assert record["lock"]["selected_rung"]["group_count"] == 26
    assert record["durability"]["mode"] == TASK2_RETRIEVAL_V4_DURABILITY
    assert "FINAL_ATOMIC_WRITE" in record["durability"]["interruption_boundary"]
    assert record["calibration_boundary"][
        "reviewed_relations_used_to_build_frozen_input"
    ] is True
    assert record["calibration_boundary"][
        "provider_call_branching_after_input_build_uses_reviewed_relations"
    ] is False
    assert record["corpus"]["provider_visible_ids"] == "CALL_LOCAL_ONLY"
    assert record["timing"]["provider_connection_seconds"] == 1.25
    assert record["timing"]["candidate_stage_call_seconds"] >= 0.0
    assert record["timing"]["verifier_stage_call_seconds"] >= 0.0
    path = (
        tmp_path
        / "task2-retrieval-v4"
        / f"{record['run_id']}-fake.json"
    )
    assert record["ledger_path"] == str(path)
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["score"]["candidate_retrieval"]["recall_at_3"] == 1.0
    assert persisted["score"]["final_group_co_membership"][
        "all_reviewed_groups"
    ]["overall"]["exact"] == 56

    gate = evaluate_task2_retrieval_v4_rung_gate(record)
    assert gate["role"] == "CONSUMED_CALIBRATION_SINGLE_RUN_RUNG_GATE"
    assert gate["passed"] is True
    assert "THREE_OF_THREE" in gate["scale_promotion_requires"]


def test_single_run_rung_gate_blocks_candidate_or_multi_member_regression(tmp_path):
    value = _value(26)
    record = run_task2_retrieval_v4_campaign(
        ReviewedFakeProvider(value),  # type: ignore[arg-type]
        ledger_dir=tmp_path,
        provider_connection_seconds=0.0,
        group_count=26,
    )
    record["score"]["candidate_retrieval"]["recall_at_3"] = 0.97
    record["score"]["grouping_diagnostics"]["reciprocal"]["score"][
        "multi_member_group_recall"
    ] = 0.5

    gate = evaluate_task2_retrieval_v4_rung_gate(record)

    assert gate["passed"] is False
    assert gate["criteria"]["candidate_recall_at_3"]["passed"] is False
    assert gate["criteria"]["multi_member_group_recall"]["passed"] is False


def test_locked_rung_batch_size_and_minimum_target_contracts_are_enforced(tmp_path):
    value = _value(26)
    provider = ReviewedFakeProvider(value)
    with pytest.raises(Task2RetrievalV4Error, match="frozen at 15"):
        task2_retrieval_v4_provider_call_count(value, batch_size=10)
    with pytest.raises(Task2RetrievalV4Error, match="frozen EN rung"):
        run_task2_retrieval_v4_campaign(
            provider,  # type: ignore[arg-type]
            ledger_dir=tmp_path,
            provider_connection_seconds=0.0,
            group_count=3,
        )
    assert provider.calls == []


def test_uuid_path_collision_never_overwrites_existing_ledger(tmp_path, monkeypatch):
    value = _value(26)
    monkeypatch.setattr(retrieval_v4, "_run_id", lambda _started: "fixed-uuid")
    first = run_task2_retrieval_v4_campaign(
        ReviewedFakeProvider(value),  # type: ignore[arg-type]
        ledger_dir=tmp_path,
        provider_connection_seconds=0.0,
        group_count=26,
    )
    path = tmp_path / "task2-retrieval-v4" / "fixed-uuid-fake.json"
    original = path.read_bytes()

    with pytest.raises(Task2RetrievalV4Error, match="already exists"):
        run_task2_retrieval_v4_campaign(
            ReviewedFakeProvider(value),  # type: ignore[arg-type]
            ledger_dir=tmp_path,
            provider_connection_seconds=0.0,
            group_count=26,
        )

    assert first["ledger_path"] == str(path)
    assert path.read_bytes() == original


def _retained_exact_record(value, ledger_dir):
    return run_task2_retrieval_v4_campaign(
        ReviewedFakeProvider(value),  # type: ignore[arg-type]
        ledger_dir=ledger_dir,
        provider_connection_seconds=0.0,
        group_count=26,
    )


def test_strict_provider_parity_accepts_two_exact_valid_ledgers(tmp_path):
    value = _value(26)
    first = _retained_exact_record(value, tmp_path / "first")
    second = _retained_exact_record(value, tmp_path / "second")
    second = json.loads(json.dumps(second))

    result = compare_task2_retrieval_v4_records(first, second)

    assert result["parity_gate_passed"] is True
    assert result["first_contract_valid"] is True
    assert result["second_contract_valid"] is True
    assert "UNSIGNED_LEDGER_INTERNAL_CONSISTENCY" in result["comparison_scope"]
    assert result["candidate_set_agreement"]["overall"] == {
        "exact": 56,
        "total": 56,
        "exact_accuracy": 1.0,
        "macro_jaccard": 1.0,
    }
    final = result["final_group_co_membership_agreement"]["overall"]
    assert final["exact"] == final["total"] == 56
    assert final["both_gold"] == 56
    reviewed = result["reviewed_one_to_one_gold_quadrants"]["overall"]
    assert reviewed["exact"] == reviewed["total"] == 48
    assert reviewed["both_gold"] == 48
    assert reviewed["first_only_gold"] == 0
    assert reviewed["second_only_gold"] == 0
    assert reviewed["both_wrong_same"] == 0
    assert reviewed["both_wrong_different"] == 0
    assert result["grouping_agreement"]["reciprocal"]["exact"] is True
    assert result["grouping_agreement"]["union"]["exact"] is True


def test_parity_accepts_matching_valid_empty_verifier_sets(tmp_path):
    value = _value(26)

    def zero_hit_provider():
        provider = ReviewedFakeProvider(value)

        def replace_first_candidate_with_three_wrong_targets(decoded):
            prompt = provider.calls[-1][0]
            payload = json.loads(prompt.split(retrieval_v4._PAYLOAD_MARKER, 1)[1])
            source = payload["sources"][0]
            expected = provider.expected[provider._fixture(source, side="left")]
            decoded["selections"][0]["target_ids"] = [
                target["id"]
                for target in payload["targets"]
                if provider._fixture(target, side="right") not in expected
            ][:3]

        provider.mutations[0] = replace_first_candidate_with_three_wrong_targets
        return provider

    first = run_task2_retrieval_v4_campaign(
        zero_hit_provider(),  # type: ignore[arg-type]
        ledger_dir=tmp_path / "first",
        provider_connection_seconds=0.0,
        group_count=26,
    )
    second = run_task2_retrieval_v4_campaign(
        zero_hit_provider(),  # type: ignore[arg-type]
        ledger_dir=tmp_path / "second",
        provider_connection_seconds=0.0,
        group_count=26,
    )

    result = compare_task2_retrieval_v4_records(first, second)

    assert result["parity_gate_passed"] is True
    assert any(not item["target_fixture_ids"] for item in first["final_selections"])
    final = result["final_group_co_membership_agreement"]["overall"]
    assert final["exact"] == final["total"] == 56
    assert final["both_wrong_same"] == 1


def test_candidate_set_difference_fails_parity_even_when_verifier_stays_gold_exact(
    tmp_path,
):
    value = _value(26)
    first = _retained_exact_record(value, tmp_path / "first")
    changed_provider = ReviewedFakeProvider(value)
    reviewed_left = {
        relation.left_fixture_ids[0]
        for relation in value.expected
        if len(relation.left_fixture_ids) == len(relation.right_fixture_ids) == 1
    }

    def replace_one_extra_candidate(decoded):
        prompt = changed_provider.calls[-1][0]
        payload = json.loads(prompt.split(retrieval_v4._PAYLOAD_MARKER, 1)[1])
        all_target_ids = [target["id"] for target in payload["targets"]]
        for source, selection in zip(payload["sources"], decoded["selections"]):
            fixture_id = changed_provider._fixture(source, side="left")
            if fixture_id not in reviewed_left:
                continue
            replacement = next(
                target_id
                for target_id in all_target_ids
                if target_id not in selection["target_ids"]
            )
            selection["target_ids"][-1] = replacement
            return
        raise AssertionError("first candidate batch has no reviewed 1:1 source")

    changed_provider.mutations[0] = replace_one_extra_candidate
    second = run_task2_retrieval_v4_campaign(
        changed_provider,  # type: ignore[arg-type]
        ledger_dir=tmp_path / "second",
        provider_connection_seconds=0.0,
        group_count=26,
    )

    result = compare_task2_retrieval_v4_records(first, second)

    assert result["parity_gate_passed"] is False
    candidate = result["candidate_set_agreement"]["overall"]
    assert candidate["exact"] == candidate["total"] - 1
    final = result["final_group_co_membership_agreement"]["overall"]
    assert final["exact"] == final["total"]


def test_final_set_difference_fails_parity_and_enters_reviewed_gold_quadrant(
    tmp_path,
):
    value = _value(26)
    first = _retained_exact_record(value, tmp_path / "first")
    changed_provider = ReviewedFakeProvider(value)
    reviewed_left = {
        relation.left_fixture_ids[0]
        for relation in value.expected
        if len(relation.left_fixture_ids) == len(relation.right_fixture_ids) == 1
    }

    def add_one_wrong_verified_candidate(decoded):
        prompt = changed_provider.calls[-1][0]
        payload = json.loads(prompt.split(retrieval_v4._PAYLOAD_MARKER, 1)[1])
        for source, selection in zip(payload["sources"], decoded["selections"]):
            fixture_id = changed_provider._fixture(source, side="left")
            if fixture_id not in reviewed_left:
                continue
            extra = next(
                candidate["id"]
                for candidate in source["candidates"]
                if candidate["id"] not in selection["target_ids"]
            )
            selection["target_ids"].append(extra)
            return
        raise AssertionError("first verifier batch has no reviewed 1:1 source")

    changed_provider.mutations[1] = add_one_wrong_verified_candidate
    second = run_task2_retrieval_v4_campaign(
        changed_provider,  # type: ignore[arg-type]
        ledger_dir=tmp_path / "second",
        provider_connection_seconds=0.0,
        group_count=26,
    )

    result = compare_task2_retrieval_v4_records(first, second)

    assert result["parity_gate_passed"] is False
    assert result["candidate_set_agreement"]["overall"]["exact"] == 56
    final = result["final_group_co_membership_agreement"]["overall"]
    assert final["exact"] == 55
    reviewed = result["reviewed_one_to_one_gold_quadrants"]["overall"]
    assert reviewed["first_only_gold"] == 1
    assert reviewed["second_only_gold"] == 0


def test_parity_rejects_mismatched_frozen_lock_rung(tmp_path):
    value = _value(26)
    first = _retained_exact_record(value, tmp_path / "first")
    second = _retained_exact_record(value, tmp_path / "second")
    second["lock"]["selected_rung"]["input_digest"] = "0" * 64

    with pytest.raises(Task2RetrievalV4Error, match="lock does not match"):
        compare_task2_retrieval_v4_records(first, second)


def test_parity_rejects_call_and_top_level_selection_inconsistency(tmp_path):
    value = _value(26)
    first = _retained_exact_record(value, tmp_path / "first")
    corrupted = copy.deepcopy(first)
    corrupted["candidate_selections"].pop()

    with pytest.raises(
        Task2RetrievalV4Error, match="call and top-level selections disagree"
    ):
        compare_task2_retrieval_v4_records(first, corrupted)


def test_parity_rejects_raw_response_digest_mutation(tmp_path):
    value = _value(26)
    first = _retained_exact_record(value, tmp_path / "first")
    corrupted = copy.deepcopy(first)
    corrupted["calls"][0]["raw_response"] += " "

    with pytest.raises(Task2RetrievalV4Error, match="raw response digest"):
        compare_task2_retrieval_v4_records(first, corrupted)
