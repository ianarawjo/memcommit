"""Contracts for bidirectional microbatched Task 2 counterpart retrieval."""
from __future__ import annotations

import hashlib
import json
import math
import re

import pytest

import memcommit.eval.task2_retrieval_v3 as retrieval_v3
from memcommit.eval.task2_discovery import (
    build_task2_discovery_input,
    load_task2_discovery_corpus,
)
from memcommit.eval.task2_retrieval_v3 import (
    LEFT_TO_RIGHT,
    RIGHT_TO_LEFT,
    TASK2_RETRIEVAL_V3_BATCH_SIZE,
    TASK2_RETRIEVAL_V3_DURABILITY,
    TASK2_RETRIEVAL_V3_GROUPING_SELECTION,
    TASK2_RETRIEVAL_V3_KIND,
    Task2RetrievalV3Error,
    Task2RetrievalV3ResponseError,
    compare_task2_retrieval_v3_records,
    discover_task2_counterparts_v3,
    evaluate_task2_retrieval_v3_promotion,
    run_task2_retrieval_v3_campaign,
    score_task2_retrieval_grouping_v3,
    task2_retrieval_v3_provider_call_count,
)
from memcommit.provider_types import CompletionRun, ProviderIdentity


class SequenceProvider:
    def __init__(self, responses: list[str | BaseException]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []
        self.identity = ProviderIdentity(
            provider="fake",
            model="fixture-model",
            model_digest="b" * 64,
            runtime="pytest",
        )
        self.last_run: CompletionRun | None = None
        self.thinking = "off"

    def complete(self, prompt, *, operation, output_schema=None):
        index = len(self.calls)
        self.calls.append((prompt, operation, output_schema))
        response = self.responses[index]
        if isinstance(response, BaseException):
            raise response
        self.last_run = CompletionRun(
            identity=self.identity,
            operation=operation,
            prompt_tokens=len(prompt.split()),
            completion_tokens=len(response.split()),
        )
        return response


def _fixture_to_alias(value) -> dict[str, str]:
    return {
        fixture_id: alias
        for alias, fixture_id in value.alias_to_fixture_id.items()
    }


def _gold_counterparts(value):
    left: dict[str, tuple[str, ...]] = {}
    right: dict[str, tuple[str, ...]] = {}
    for relation in value.expected:
        for fixture_id in relation.left_fixture_ids:
            left[fixture_id] = relation.right_fixture_ids
        for fixture_id in relation.right_fixture_ids:
            right[fixture_id] = relation.left_fixture_ids
    return left, right


def _gold_responses(value, *, batch_size=TASK2_RETRIEVAL_V3_BATCH_SIZE):
    fixture_to_alias = _fixture_to_alias(value)
    left_expected, right_expected = _gold_counterparts(value)
    responses: list[str] = []
    for items, expected in (
        (value.left_items, left_expected),
        (value.right_items, right_expected),
    ):
        for start in range(0, len(items), batch_size):
            batch = items[start : start + batch_size]
            responses.append(
                json.dumps(
                    {
                        "selections": [
                            {
                                "source_id": item["id"],
                                "target_ids": [
                                    fixture_to_alias[target]
                                    for target in expected[
                                        value.alias_to_fixture_id[item["id"]]
                                    ]
                                ],
                            }
                            for item in batch
                        ]
                    }
                )
            )
    return responses


def test_full_150_by_150_schedule_has_fixed_inference_path_and_exact_score():
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=138
    )
    provider = SequenceProvider(_gold_responses(value))

    run = discover_task2_counterparts_v3(provider, value)  # type: ignore[arg-type]

    assert len(value.left_items) == len(value.right_items) == 150
    assert len(provider.calls) == run.provider_call_count == 20
    assert run.expected_provider_call_count == (
        math.ceil(150 / TASK2_RETRIEVAL_V3_BATCH_SIZE) * 2
    )
    assert run.contract_valid is True
    score = run.score["group_co_membership_retrieval"]
    assert score["metric"] == "GROUP_CO_MEMBERSHIP_RETRIEVAL"
    assert score["atomic_semantic_pair_gold"] is False
    reviewed = score["reviewed_one_to_one_subset"]
    assert reviewed["directed_edge_gold_available"] is True
    assert reviewed["overall"] == {
        "exact": 258,
        "total": 258,
        "exact_accuracy": 1.0,
        "macro_jaccard": 1.0,
    }
    co_membership = score["group_co_membership"]
    assert co_membership["reviewed_group_membership_gold_available"] is True
    assert co_membership["directed_edge_gold_available"] is False
    assert co_membership["left"]["exact_accuracy"] == 1.0
    assert co_membership["right"]["exact_accuracy"] == 1.0
    assert co_membership["overall"] == {
        "exact": 300,
        "total": 300,
        "exact_accuracy": 1.0,
        "macro_jaccard": 1.0,
    }
    assert all(
        call.source_stop - call.source_start <= TASK2_RETRIEVAL_V3_BATCH_SIZE
        for call in run.calls
    )
    assert all(call.target_count == 150 for call in run.calls)
    assert [call.call_index for call in run.calls] == list(range(1, 21))
    assert [call.direction for call in run.calls[:10]] == [LEFT_TO_RIGHT] * 10
    assert [call.direction for call in run.calls[10:]] == [RIGHT_TO_LEFT] * 10
    assert [call.source_start for call in run.calls[:10]] == list(range(0, 150, 15))
    assert [call.source_start for call in run.calls[10:]] == list(range(0, 150, 15))
    assert all(call.raw_response for call in run.calls)
    assert all(call.prompt_digest and call.schema_digest for call in run.calls)
    assert all(
        call.response_digest == hashlib.sha256(call.raw_response.encode()).hexdigest()
        for call in run.calls
    )
    assert all(call.elapsed_seconds >= 0.0 for call in run.calls)
    assert all(
        selection.source_fixture_id.startswith("T2-")
        and all(target.startswith("T2-") for target in selection.target_fixture_ids)
        for selection in run.selections
    )

    aliases = set(value.alias_to_fixture_id)
    fixture_ids = set(value.alias_to_fixture_id.values())
    for index, (prompt, operation, schema) in enumerate(provider.calls):
        assert "group co-membership retrieval" in operation
        assert schema is not None
        assert "band" not in json.dumps(schema).lower()
        assert "uniqueItems" not in json.dumps(schema)
        assert "all and only the opposite-side Memories" in prompt
        assert "Rank every retained group co-member" in prompt
        assert fixture_ids.isdisjoint(set(prompt.split('"')))
        direction = LEFT_TO_RIGHT if index < 10 else RIGHT_TO_LEFT
        targets = value.right_items if direction == LEFT_TO_RIGHT else value.left_items
        assert {item["id"] for item in targets} <= set(prompt.split('"'))
        assert aliases & set(prompt.split('"'))

    for name in ("reciprocal", "union"):
        diagnostic = run.score["grouping_diagnostics"][name]
        assert diagnostic["score"]["exact_complete_grouping"] is True
        assert (
            diagnostic["score"]["member_counterpart_sets"]["overall"]
            ["exact_accuracy"]
            == 1.0
        )


def test_invalid_batch_is_retained_and_all_later_fixed_calls_still_run():
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=26
    )
    responses = _gold_responses(value)
    responses[0] = json.dumps({"selections": []})
    provider = SequenceProvider(responses)

    with pytest.raises(
        Task2RetrievalV3ResponseError, match="every batch source_id exactly once"
    ) as captured:
        discover_task2_counterparts_v3(provider, value)  # type: ignore[arg-type]

    run = captured.value.run
    assert len(provider.calls) == run.provider_call_count == 4
    assert run.expected_provider_call_count == 4
    assert run.contract_valid is False
    assert run.calls[0].contract_valid is False
    assert run.calls[0].raw_response == responses[0]
    assert run.calls[0].selections == ()
    assert all(call.contract_valid for call in run.calls[1:])
    assert len(run.selections) == 56 - len(run.calls[0].source_fixture_ids)
    assert (
        run.score["group_co_membership_retrieval"]["group_co_membership"]
        ["overall"]["exact_accuracy"]
        < 1.0
    )


@pytest.mark.parametrize("bad_target", ["duplicate", "unknown"])
def test_ranked_targets_must_be_valid_and_unique(bad_target):
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=3
    )
    responses = _gold_responses(value)
    first = json.loads(responses[0])
    if bad_target == "duplicate":
        target = first["selections"][0]["target_ids"][0]
        first["selections"][0]["target_ids"] = [target, target]
    else:
        first["selections"][0]["target_ids"] = ["not-an-input-alias"]
    responses[0] = json.dumps(first)
    provider = SequenceProvider(responses)

    with pytest.raises(
        Task2RetrievalV3ResponseError, match="ranked target_ids"
    ) as captured:
        discover_task2_counterparts_v3(provider, value)  # type: ignore[arg-type]

    assert len(provider.calls) == 2
    assert captured.value.run.calls[0].contract_valid is False
    assert captured.value.run.calls[1].contract_valid is True


def test_reciprocal_and_union_groupings_are_both_retained_without_gold_selection():
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=2
    )
    aliases = _fixture_to_alias(value)
    left_by_fixture = {
        value.alias_to_fixture_id[item["id"]]: item["id"] for item in value.left_items
    }
    right_by_fixture = {
        value.alias_to_fixture_id[item["id"]]: item["id"] for item in value.right_items
    }
    left_response = {
        "selections": [
            {
                "source_id": left_by_fixture["T2-L-001"],
                "target_ids": [aliases["T2-R-001"]],
            },
            {
                "source_id": left_by_fixture["T2-L-002"],
                "target_ids": [aliases["T2-R-002"]],
            },
        ]
    }
    right_response = {
        "selections": [
            {
                "source_id": right_by_fixture["T2-R-001"],
                "target_ids": [aliases["T2-L-001"]],
            },
            {
                "source_id": right_by_fixture["T2-R-002"],
                "target_ids": [aliases["T2-L-001"]],
            },
        ]
    }
    provider = SequenceProvider(
        [json.dumps(left_response), json.dumps(right_response)]
    )

    run = discover_task2_counterparts_v3(provider, value)  # type: ignore[arg-type]

    assert run.grouping_selection == TASK2_RETRIEVAL_V3_GROUPING_SELECTION
    assert "BEST" not in run.grouping_selection
    assert run.reciprocal_groups != run.union_groups
    diagnostics = run.score["grouping_diagnostics"]
    assert set(diagnostics) == {"reciprocal", "union"}
    assert diagnostics["reciprocal"]["score"]["exact_groups"] == 1
    assert diagnostics["union"]["score"]["exact_groups"] == 0
    assert (
        run.score["group_co_membership_retrieval"]["reviewed_one_to_one_subset"]
        ["left"]["exact_accuracy"]
        == 1.0
    )
    assert (
        run.score["group_co_membership_retrieval"]["reviewed_one_to_one_subset"]
        ["right"]["exact_accuracy"]
        == 0.5
    )


def test_empty_group_prediction_has_zero_precision():
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=2
    )

    score = score_task2_retrieval_grouping_v3(value, ())

    assert score["predicted_components"] == 0
    assert score["exact_groups"] == 0
    assert score["exact_group_precision"] == 0.0
    assert score["exact_group_recall"] == 0.0
    assert score["exact_group_f1"] == 0.0


def test_campaign_retains_valid_frozen_en_attempt(tmp_path):
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=26
    )
    provider = SequenceProvider(_gold_responses(value))

    record = run_task2_retrieval_v3_campaign(
        provider,  # type: ignore[arg-type]
        ledger_dir=tmp_path,
        provider_connection_seconds=1.5,
        group_count=26,
    )

    assert record["kind"] == TASK2_RETRIEVAL_V3_KIND
    assert re.fullmatch(r"\d{8}T\d{12}Z-[0-9a-f]{32}", record["run_id"])
    assert record["status"] == "VALID"
    assert record["contract_valid"] is True
    assert record["provider_call_count"] == record["expected_provider_call_count"] == 4
    assert record["lock"]["corpus_locked"] is True
    assert record["lock"]["slice_locked"] is True
    assert record["lock"]["selected_slice"]["group_count"] == 26
    assert record["corpus"]["selected_left_count"] == 29
    assert record["corpus"]["selected_right_count"] == 27
    assert len(record["calls"]) == 4
    assert record["calls"][0]["raw_response"] == provider.responses[0]
    assert record["grouping_selection"] == TASK2_RETRIEVAL_V3_GROUPING_SELECTION
    assert record["durability"]["mode"] == TASK2_RETRIEVAL_V3_DURABILITY
    assert "FINAL_ATOMIC_WRITE" in record["durability"]["interruption_boundary"]
    assert record["calibration_boundary"] == {
        "input_membership": "PREFIX_OF_COMPLETE_REVIEWED_GROUPS",
        "maximum_targets": (
            "MAXIMUM_OPPOSITE_MEMBER_CARDINALITY_IN_CONSUMED_CALIBRATION"
        ),
        "prompt_and_control_flow_gold_blind_after_input_freeze": True,
        "independent_holdout": False,
    }
    assert set(record["groupings"]) == {"reciprocal", "union"}
    assert record["score"]["group_co_membership_retrieval"][
        "reviewed_one_to_one_subset"
    ][
        "overall"
    ] == {
        "exact": 48,
        "total": 48,
        "exact_accuracy": 1.0,
        "macro_jaccard": 1.0,
    }
    assert record["score"]["group_co_membership_retrieval"][
        "group_co_membership"
    ]["overall"] == {
        "exact": 56,
        "total": 56,
        "exact_accuracy": 1.0,
        "macro_jaccard": 1.0,
    }
    assert record["timing"]["provider_connection_seconds"] == 1.5
    path = tmp_path / "task2-retrieval-v3" / f"{record['run_id']}-fake.json"
    assert record["ledger_path"] == str(path)
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["status"] == "VALID"
    assert persisted["calls"][0]["response_digest"] == record["calls"][0]["response_digest"]
    promotion = evaluate_task2_retrieval_v3_promotion(record)
    assert promotion["passed"] is True
    assert (
        promotion["criteria"]["co_membership_micro_recall"]["actual"] == 1.0
    )


def test_campaign_retains_invalid_output_instead_of_losing_the_run(tmp_path):
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=26
    )
    responses = _gold_responses(value)
    responses[-1] = "not json"
    provider = SequenceProvider(responses)

    record = run_task2_retrieval_v3_campaign(
        provider,  # type: ignore[arg-type]
        ledger_dir=tmp_path,
        provider_connection_seconds=0.25,
        group_count=26,
    )

    assert len(provider.calls) == 4
    assert record["status"] == "INVALID_OUTPUT"
    assert record["contract_valid"] is False
    assert "invalid strict JSON" in record["validation_error"]
    assert record["calls"][-1]["raw_response"] == "not json"
    assert record["calls"][-1]["contract_valid"] is False
    path = tmp_path / "task2-retrieval-v3" / f"{record['run_id']}-fake.json"
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["status"] == "INVALID_OUTPUT"
    assert persisted["calls"][-1]["response_digest"] == hashlib.sha256(
        b"not json"
    ).hexdigest()
    assert evaluate_task2_retrieval_v3_promotion(record)["passed"] is False


def test_campaign_retains_configured_transport_failure_without_its_message(tmp_path):
    class SecretTransportError(RuntimeError):
        pass

    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=26
    )
    responses: list[str | BaseException] = _gold_responses(value)
    responses[1] = SecretTransportError("secret-token-and-request-body")
    provider = SequenceProvider(responses)

    record = run_task2_retrieval_v3_campaign(
        provider,  # type: ignore[arg-type]
        ledger_dir=tmp_path,
        provider_connection_seconds=0.25,
        group_count=26,
        known_error_types=(SecretTransportError,),
    )

    assert len(provider.calls) == 4
    assert record["status"] == "PROVIDER_ERROR"
    assert record["contract_valid"] is False
    failed = record["calls"][1]
    assert failed["direction"] == LEFT_TO_RIGHT
    assert failed["direction_batch_index"] == 2
    assert failed["source_start"] == 15
    assert failed["source_stop"] == 29
    assert failed["failure_category"] == "PROVIDER"
    assert failed["error_type"] == "SecretTransportError"
    assert failed["raw_response"] is None
    assert failed["response_digest"] is None
    assert failed["prompt_digest"]
    assert failed["schema_digest"]
    assert failed["provider_completion_seconds"] >= 0.0
    assert all(call["contract_valid"] for call in record["calls"] if call is not failed)
    path = tmp_path / "task2-retrieval-v3" / f"{record['run_id']}-fake.json"
    persisted_text = path.read_text(encoding="utf-8")
    assert "secret-token-and-request-body" not in persisted_text
    assert "SecretTransportError" in persisted_text


def test_existing_uuid_ledger_path_is_never_overwritten(tmp_path, monkeypatch):
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=26
    )
    monkeypatch.setattr(retrieval_v3, "_run_id", lambda _started: "fixed-uuid")
    first = run_task2_retrieval_v3_campaign(
        SequenceProvider(_gold_responses(value)),  # type: ignore[arg-type]
        ledger_dir=tmp_path,
        provider_connection_seconds=0.0,
        group_count=26,
    )
    path = tmp_path / "task2-retrieval-v3" / "fixed-uuid-fake.json"
    original = path.read_bytes()

    with pytest.raises(Task2RetrievalV3Error, match="already exists"):
        run_task2_retrieval_v3_campaign(
            SequenceProvider(_gold_responses(value)),  # type: ignore[arg-type]
            ledger_dir=tmp_path,
            provider_connection_seconds=0.0,
            group_count=26,
        )

    assert first["ledger_path"] == str(path)
    assert path.read_bytes() == original


def test_batch_size_is_frozen_at_fifteen_and_campaign_requires_locked_slice(tmp_path):
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=3
    )
    with pytest.raises(Task2RetrievalV3Error, match="frozen at 15"):
        task2_retrieval_v3_provider_call_count(value, batch_size=16)
    with pytest.raises(Task2RetrievalV3Error, match="frozen at 15"):
        task2_retrieval_v3_provider_call_count(value, batch_size=10)
    provider = SequenceProvider([])
    with pytest.raises(Task2RetrievalV3Error, match="frozen EN slice"):
        run_task2_retrieval_v3_campaign(
            provider,  # type: ignore[arg-type]
            ledger_dir=tmp_path,
            provider_connection_seconds=0.0,
            group_count=3,
        )
    assert provider.calls == []


def test_counterpart_parity_compares_same_sources_and_gold_quadrants(tmp_path):
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=26
    )
    first = run_task2_retrieval_v3_campaign(
        SequenceProvider(_gold_responses(value)),  # type: ignore[arg-type]
        ledger_dir=tmp_path / "first",
        provider_connection_seconds=0.0,
        group_count=26,
    )
    second = run_task2_retrieval_v3_campaign(
        SequenceProvider(_gold_responses(value)),  # type: ignore[arg-type]
        ledger_dir=tmp_path / "second",
        provider_connection_seconds=0.0,
        group_count=26,
    )

    result = compare_task2_retrieval_v3_records(first, second)

    assert result["parity_gate_passed"] is True
    assert result["group_co_membership_agreement"]["overall"] == {
        "exact": 56,
        "total": 56,
        "exact_accuracy": 1.0,
        "macro_jaccard": 1.0,
        "both_gold": 56,
        "first_only_gold": 0,
        "second_only_gold": 0,
        "both_wrong_same": 0,
        "both_wrong_different": 0,
    }
    assert result["grouping_agreement"]["reciprocal"]["exact"] is True
    assert result["grouping_agreement"]["union"]["exact"] is True


def test_counterpart_parity_detects_provider_disagreement_without_repair(tmp_path):
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=26
    )
    first = run_task2_retrieval_v3_campaign(
        SequenceProvider(_gold_responses(value)),  # type: ignore[arg-type]
        ledger_dir=tmp_path / "first",
        provider_connection_seconds=0.0,
        group_count=26,
    )
    responses = _gold_responses(value)
    changed = json.loads(responses[0])
    original_aliases = changed["selections"][0]["target_ids"]
    all_right_aliases = [item["id"] for item in value.right_items]
    alternative_alias = next(
        alias for alias in all_right_aliases if alias not in original_aliases
    )
    changed["selections"][0]["target_ids"] = [alternative_alias]
    responses[0] = json.dumps(changed)
    second = run_task2_retrieval_v3_campaign(
        SequenceProvider(responses),  # type: ignore[arg-type]
        ledger_dir=tmp_path / "second",
        provider_connection_seconds=0.0,
        group_count=26,
    )

    result = compare_task2_retrieval_v3_records(first, second)

    overall = result["group_co_membership_agreement"]["overall"]
    assert result["parity_gate_passed"] is False
    assert overall["exact"] == 55
    assert overall["both_gold"] == 55
    assert overall["first_only_gold"] == 1
    assert overall["second_only_gold"] == 0


def test_counterpart_parity_rejects_different_frozen_schedule(tmp_path):
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=26
    )
    first = run_task2_retrieval_v3_campaign(
        SequenceProvider(_gold_responses(value)),  # type: ignore[arg-type]
        ledger_dir=tmp_path / "first",
        provider_connection_seconds=0.0,
        group_count=26,
    )
    second = run_task2_retrieval_v3_campaign(
        SequenceProvider(_gold_responses(value)),  # type: ignore[arg-type]
        ledger_dir=tmp_path / "second",
        provider_connection_seconds=0.0,
        group_count=26,
    )
    second["calls"][0]["prompt_digest"] = "0" * 64

    with pytest.raises(Task2RetrievalV3Error, match="different frozen schedules"):
        compare_task2_retrieval_v3_records(first, second)


def test_counterpart_parity_rejects_false_validity_with_missing_source(tmp_path):
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=26
    )
    first = run_task2_retrieval_v3_campaign(
        SequenceProvider(_gold_responses(value)),  # type: ignore[arg-type]
        ledger_dir=tmp_path / "first",
        provider_connection_seconds=0.0,
        group_count=26,
    )
    corrupted = json.loads(json.dumps(first))
    corrupted["selections"].pop()

    with pytest.raises(
        Task2RetrievalV3Error,
        match="incomplete source partition|top-level selections disagree",
    ):
        compare_task2_retrieval_v3_records(first, corrupted)


def test_counterpart_parity_recomputes_expected_call_count(tmp_path):
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=26
    )
    first = run_task2_retrieval_v3_campaign(
        SequenceProvider(_gold_responses(value)),  # type: ignore[arg-type]
        ledger_dir=tmp_path / "first",
        provider_connection_seconds=0.0,
        group_count=26,
    )
    corrupted = json.loads(json.dumps(first))
    corrupted["expected_provider_call_count"] = 3
    corrupted["provider_call_count"] = 3
    corrupted["calls"] = corrupted["calls"][:3]

    with pytest.raises(Task2RetrievalV3Error, match="expected call count"):
        compare_task2_retrieval_v3_records(first, corrupted)


@pytest.mark.parametrize("tamper", ["raw", "nested"])
def test_counterpart_parity_rejects_contradictory_call_evidence(tmp_path, tamper):
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=26
    )
    first = run_task2_retrieval_v3_campaign(
        SequenceProvider(_gold_responses(value)),  # type: ignore[arg-type]
        ledger_dir=tmp_path / "first",
        provider_connection_seconds=0.0,
        group_count=26,
    )
    corrupted = json.loads(json.dumps(first))
    if tamper == "raw":
        corrupted["calls"][0]["raw_response"] = "{}"
    else:
        corrupted["calls"][0]["selections"] = []

    with pytest.raises(Task2RetrievalV3Error, match="response digest|call evidence"):
        compare_task2_retrieval_v3_records(first, corrupted)


def test_counterpart_parity_requires_matching_frozen_lock(tmp_path):
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=26
    )
    first = run_task2_retrieval_v3_campaign(
        SequenceProvider(_gold_responses(value)),  # type: ignore[arg-type]
        ledger_dir=tmp_path / "first",
        provider_connection_seconds=0.0,
        group_count=26,
    )
    corrupted = json.loads(json.dumps(first))
    corrupted.pop("lock")

    with pytest.raises(Task2RetrievalV3Error, match="frozen calibration lock"):
        compare_task2_retrieval_v3_records(first, corrupted)
