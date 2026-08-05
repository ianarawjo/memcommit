"""Contracts for the candidate-only Task 2 top-K ablation v5."""
from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import re

import pytest

import memcommit.eval.task2_candidate_ablation_v5 as ablation_v5
from memcommit.eval.task2_candidate_ablation_v5 import (
    LEFT_TO_RIGHT,
    RIGHT_TO_LEFT,
    TASK2_CANDIDATE_ABLATION_V5_BATCH_SIZE,
    TASK2_CANDIDATE_ABLATION_V5_DURABILITY,
    Task2CandidateAblationV5Error,
    Task2CandidateAblationV5ResponseError,
    discover_task2_candidates_v5,
    run_task2_candidate_ablation_v5_campaign,
    task2_candidate_ablation_v5_provider_call_count,
    validate_task2_candidate_ablation_v5_record,
)
from memcommit.eval.task2_discovery import (
    build_task2_discovery_input,
    load_task2_discovery_corpus,
)
from memcommit.provider_types import CompletionRun, ProviderIdentity


class ReviewedCandidateProvider:
    """Fixture teacher that reasons from displayed text and call-local IDs."""

    def __init__(self, value, *, mutations=None) -> None:
        self.identity = ProviderIdentity(
            provider="fake",
            model="reviewed-candidate-teacher",
            model_digest="d" * 64,
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
            self.left_fixture_by_text
            if side == "left"
            else self.right_fixture_by_text
        )
        return fixture_by_text[(item["topic"], item["content"])]

    def _answer(self, prompt: str) -> tuple[dict[str, object], dict[str, object]]:
        payload = json.loads(prompt.split(ablation_v5._PAYLOAD_MARKER, 1)[1])
        source_side, target_side = (
            ("left", "right")
            if payload["direction"] == LEFT_TO_RIGHT
            else ("right", "left")
        )
        candidate_count = payload["candidate_count"]
        targets = payload["targets"]
        selections = []
        for source in payload["sources"]:
            expected = self.expected[self._fixture(source, side=source_side)]
            target_by_fixture = {
                self._fixture(target, side=target_side): target["id"]
                for target in targets
            }
            selected = [target_by_fixture[item] for item in sorted(expected)]
            selected.extend(
                target["id"] for target in targets if target["id"] not in selected
            )
            selections.append(
                {
                    "source_id": source["id"],
                    "target_ids": selected[:candidate_count],
                }
            )
        return {"selections": selections}, payload

    def complete(self, prompt, *, operation, output_schema=None):
        call_index = len(self.calls)
        self.calls.append((prompt, operation, output_schema))
        mutation = self.mutations.get(call_index)
        if isinstance(mutation, BaseException):
            raise mutation
        decoded, payload = self._answer(prompt)
        if mutation is not None:
            mutation(decoded, payload, self)
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


def test_full_150_by_150_teacher_uses_20_calls_and_recovers_all_gold_edges():
    value = _value(138)
    provider = ReviewedCandidateProvider(value)

    run = discover_task2_candidates_v5(
        provider, value, candidate_count=4  # type: ignore[arg-type]
    )

    assert len(value.left_items) == len(value.right_items) == 150
    assert run.provider_call_count == len(provider.calls) == 20
    assert run.expected_provider_call_count == (
        math.ceil(150 / TASK2_CANDIDATE_ABLATION_V5_BATCH_SIZE) * 2
    )
    assert task2_candidate_ablation_v5_provider_call_count(value) == 20
    assert [call.direction for call in run.calls[:10]] == [LEFT_TO_RIGHT] * 10
    assert [call.direction for call in run.calls[10:]] == [RIGHT_TO_LEFT] * 10
    assert len(run.selections) == 300
    overall = run.score["overall"]
    assert overall["source_total"] == 300
    assert overall["expected_directed_edges"] == 362
    assert overall["micro_recall_at_k"] == 1.0
    assert overall["macro_source_recall_at_k"] == 1.0
    assert overall["one_to_one"]["recall_at_k"] == 1.0
    assert overall["multi_member_groups"]["recall_at_k"] == 1.0
    assert overall["source_hit_distribution"] == {
        "complete": 300,
        "partial": 0,
        "zero_hit": 0,
    }
    edges = run.score["unique_undirected_gold_edge_recoverability"]
    assert edges == {
        "mechanical_definition": (
            "GOLD_CARTESIAN_EDGE_PRESENT_IN_AT_LEAST_ONE_RETRIEVAL_DIRECTION"
        ),
        "recovered": 181,
        "expected": 181,
        "recall_at_k": 1.0,
    }
    groups = run.score["exact_group_recoverability"]
    assert groups["recoverable"] == groups["expected"] == 138
    assert groups["multi_member"] == {
        "recoverable": 9,
        "expected": 9,
        "recall_at_k": 1.0,
    }
    assert len(run.score["call_diagnostics"]) == 20
    assert all(item["micro_recall_at_k"] == 1.0 for item in run.score["call_diagnostics"])


def test_k4_and_k5_are_distinct_conditions_with_one_shared_prompt_template():
    value = _value()
    provider4 = ReviewedCandidateProvider(value)
    provider5 = ReviewedCandidateProvider(value)

    run4 = discover_task2_candidates_v5(
        provider4, value, candidate_count=4  # type: ignore[arg-type]
    )
    run5 = discover_task2_candidates_v5(
        provider5, value, candidate_count=5  # type: ignore[arg-type]
    )

    assert run4.condition_id == "TOP_4"
    assert run5.condition_id == "TOP_5"
    assert run4.provider_call_count == run5.provider_call_count == 4
    assert all(len(item.target_fixture_ids) == 4 for item in run4.selections)
    assert all(len(item.target_fixture_ids) == 5 for item in run5.selections)
    schema4 = provider4.calls[0][2]
    schema5 = provider5.calls[0][2]
    assert schema4["properties"]["selections"]["items"]["properties"][
        "target_ids"
    ]["minItems"] == 4
    assert schema5["properties"]["selections"]["items"]["properties"][
        "target_ids"
    ]["minItems"] == 5
    normalized4 = re.sub(
        r"TOP_[45]|(?<![A-Za-z0-9])[45](?![A-Za-z0-9])",
        "K",
        provider4.calls[0][0],
    )
    normalized5 = re.sub(
        r"TOP_[45]|(?<![A-Za-z0-9])[45](?![A-Za-z0-9])",
        "K",
        provider5.calls[0][0],
    )
    assert normalized4 == normalized5


def test_reviewed_relations_do_not_change_calls_after_the_input_is_built():
    value = _value()
    reordered_gold = replace(value, expected=tuple(reversed(value.expected)))
    first = ReviewedCandidateProvider(value)
    second = ReviewedCandidateProvider(value)

    first_run = discover_task2_candidates_v5(
        first, value, candidate_count=4  # type: ignore[arg-type]
    )
    second_run = discover_task2_candidates_v5(
        second, reordered_gold, candidate_count=4  # type: ignore[arg-type]
    )

    assert [item[:2] for item in first.calls] == [item[:2] for item in second.calls]
    assert [item[2] for item in first.calls] == [item[2] for item in second.calls]
    assert first_run.selections == second_run.selections
    assert first_run.score["overall"] == second_run.score["overall"]


def test_misses_report_zero_partial_and_recoverability_without_changing_schedule():
    value = _value()
    changed = {"zero": False, "partial": False}
    suppressed_edges = set()

    def inject_misses(decoded, payload, provider):
        source_side, target_side = (
            ("left", "right")
            if payload["direction"] == LEFT_TO_RIGHT
            else ("right", "left")
        )
        fixture_by_target = {
            item["id"]: provider._fixture(item, side=target_side)
            for item in payload["targets"]
        }
        source_by_id = {item["id"]: item for item in payload["sources"]}
        for selection in decoded["selections"]:
            source = source_by_id[selection["source_id"]]
            source_fixture = provider._fixture(source, side=source_side)
            expected = provider.expected[source_fixture]
            extras = [
                target_id
                for target_id, fixture_id in fixture_by_target.items()
                if fixture_id not in expected
            ]
            if (
                payload["direction"] == LEFT_TO_RIGHT
                and len(expected) == 1
                and not changed["zero"]
            ):
                suppressed_edges.add((source_fixture, next(iter(expected))))
                changed["zero"] = True
            elif (
                payload["direction"] == LEFT_TO_RIGHT
                and len(expected) > 1
                and not changed["partial"]
            ):
                suppressed_edges.update(
                    (source_fixture, target_fixture)
                    for target_fixture in sorted(expected)[1:]
                )
                changed["partial"] = True
            retained = []
            for target_id in selection["target_ids"]:
                target_fixture = fixture_by_target[target_id]
                edge = (
                    (source_fixture, target_fixture)
                    if payload["direction"] == LEFT_TO_RIGHT
                    else (target_fixture, source_fixture)
                )
                if edge not in suppressed_edges:
                    retained.append(target_id)
            retained.extend(
                target_id
                for target_id in extras
                if target_id not in retained
            )
            selection["target_ids"] = retained[: payload["candidate_count"]]

    provider = ReviewedCandidateProvider(
        value, mutations={index: inject_misses for index in range(4)}
    )

    run = discover_task2_candidates_v5(
        provider, value, candidate_count=4  # type: ignore[arg-type]
    )

    assert changed == {"zero": True, "partial": True}
    assert run.provider_call_count == 4
    distribution = run.score["overall"]["source_hit_distribution"]
    assert distribution["zero_hit"] >= 1
    assert distribution["partial"] >= 1
    assert run.score["overall"]["one_to_one"]["recall_at_k"] < 1.0
    assert run.score["overall"]["multi_member_groups"]["recall_at_k"] < 1.0
    assert run.score["unique_undirected_gold_edge_recoverability"]["recall_at_k"] < 1.0
    assert run.score["exact_group_recoverability"]["recall_at_k"] < 1.0


@pytest.mark.parametrize(
    "mutation, message",
    [
        (
            lambda decoded, _payload, _provider: decoded["selections"][0][
                "target_ids"
            ].__setitem__(0, "t999"),
            "invalid or duplicate",
        ),
        (
            lambda decoded, _payload, _provider: decoded["selections"][0][
                "target_ids"
            ].__setitem__(
                1, decoded["selections"][0]["target_ids"][0]
            ),
            "invalid or duplicate",
        ),
        (
            lambda decoded, _payload, _provider: decoded["selections"].pop(),
            "every call-local source_id",
        ),
    ],
    ids=["unknown-target", "duplicate-target", "omitted-source"],
)
def test_invalid_id_duplicate_and_omission_fail_closed_after_all_four_calls(
    mutation, message
):
    value = _value()
    provider = ReviewedCandidateProvider(value, mutations={0: mutation})

    with pytest.raises(Task2CandidateAblationV5ResponseError, match=message) as caught:
        discover_task2_candidates_v5(
            provider, value, candidate_count=4  # type: ignore[arg-type]
        )

    run = caught.value.run
    assert len(provider.calls) == run.provider_call_count == 4
    assert run.calls[0].contract_valid is False
    assert run.calls[0].failure_category == "INVALID_OUTPUT"
    assert all(call.contract_valid for call in run.calls[1:])
    assert run.score["call_diagnostics"][0]["source_hit_distribution"][
        "zero_hit"
    ] == 15


def test_known_provider_error_is_redacted_and_remaining_schedule_continues():
    value = _value()
    provider = ReviewedCandidateProvider(
        value,
        mutations={0: RuntimeError("secret endpoint and token")},
    )

    with pytest.raises(Task2CandidateAblationV5ResponseError) as caught:
        discover_task2_candidates_v5(
            provider,
            value,
            candidate_count=5,
            known_error_types=(RuntimeError,),  # type: ignore[arg-type]
        )

    run = caught.value.run
    assert len(provider.calls) == run.provider_call_count == 4
    failed = run.calls[0]
    assert failed.failure_category == "PROVIDER"
    assert failed.error_type == "RuntimeError"
    assert failed.raw_response is failed.response_digest is None
    assert "secret" not in (run.validation_error or "")
    assert all(call.contract_valid for call in run.calls[1:])


def test_provider_boundary_uses_only_fresh_call_local_ids_and_retains_host_mapping():
    value = _value()
    provider = ReviewedCandidateProvider(value)

    run = discover_task2_candidates_v5(
        provider, value, candidate_count=4  # type: ignore[arg-type]
    )

    fixture_ids = set(value.alias_to_fixture_id.values())
    opaque_aliases = set(value.alias_to_fixture_id)
    for index, (prompt, _operation, _schema) in enumerate(provider.calls):
        payload = json.loads(prompt.split(ablation_v5._PAYLOAD_MARKER, 1)[1])
        assert [item["id"] for item in payload["sources"]] == [
            f"s{item:02d}" for item in range(1, len(payload["sources"]) + 1)
        ]
        assert [item["id"] for item in payload["targets"]] == [
            f"t{item:03d}" for item in range(1, len(payload["targets"]) + 1)
        ]
        assert not any(item in prompt for item in fixture_ids | opaque_aliases)
        call = run.calls[index]
        assert call.local_source_mapping[0][0] == "s01"
        assert call.local_target_mapping[0][0] == "t001"
        assert call.response_digest == hashlib.sha256(
            call.raw_response.encode()
        ).hexdigest()
        assert re.fullmatch(r"[0-9a-f]{64}", call.local_id_mapping_digest)
        raw = json.loads(call.raw_response)
        assert all(
            re.fullmatch(r"s\d{2}", item["source_id"])
            and all(re.fullmatch(r"t\d{3}", target) for target in item["target_ids"])
            for item in raw["selections"]
        )


def test_campaign_retains_distinct_uuid_conditions_and_auditable_provenance(tmp_path):
    value = _value()
    record4 = run_task2_candidate_ablation_v5_campaign(
        ReviewedCandidateProvider(value),  # type: ignore[arg-type]
        ledger_dir=tmp_path,
        provider_connection_seconds=0.25,
        candidate_count=4,
    )
    record5 = run_task2_candidate_ablation_v5_campaign(
        ReviewedCandidateProvider(value),  # type: ignore[arg-type]
        ledger_dir=tmp_path,
        provider_connection_seconds=0.5,
        candidate_count=5,
    )

    assert record4["condition"]["id"] == "TOP_4"
    assert record5["condition"]["id"] == "TOP_5"
    assert record4["durability"]["mode"] == TASK2_CANDIDATE_ABLATION_V5_DURABILITY
    assert record4["calibration_boundary"][
        "provider_call_branching_after_input_build_uses_reviewed_relations"
    ] is False
    assert record4["provider_call_count"] == record5["provider_call_count"] == 4
    path4 = Path(record4["ledger_path"])
    path5 = Path(record5["ledger_path"])
    assert path4 != path5
    assert "top_4" in path4.name and "top_5" in path5.name
    assert re.search(r"-[0-9a-f]{32}-top_[45]-fake\.json$", path4.name)
    assert record4["timing"]["total_seconds"] >= 0.25
    assert all(value >= 0 for value in record4["timing"].values())

    loaded4 = json.loads(path4.read_text())
    loaded5 = json.loads(path5.read_text())
    assert validate_task2_candidate_ablation_v5_record(loaded4) == {
        "valid": True,
        "condition_id": "TOP_4",
        "candidate_count": 4,
        "provider_call_count": 4,
        "contract_valid": True,
        "provenance_boundary": (
            "UNSIGNED_INTERNAL_CONSISTENCY_NOT_TAMPER_EVIDENT_AUTHENTICITY"
        ),
    }
    assert validate_task2_candidate_ablation_v5_record(loaded5)[
        "condition_id"
    ] == "TOP_5"


def test_provenance_validator_rejects_raw_mapping_and_normalization_tampering(tmp_path):
    value = _value()
    record = run_task2_candidate_ablation_v5_campaign(
        ReviewedCandidateProvider(value),  # type: ignore[arg-type]
        ledger_dir=tmp_path,
        provider_connection_seconds=0.0,
        candidate_count=4,
    )
    loaded = json.loads(Path(record["ledger_path"]).read_text())

    raw_tamper = copy.deepcopy(loaded)
    raw_tamper["calls"][0]["raw_response"] += " "
    with pytest.raises(Task2CandidateAblationV5Error, match="response digest"):
        validate_task2_candidate_ablation_v5_record(raw_tamper)

    mapping_tamper = copy.deepcopy(loaded)
    mapping_tamper["calls"][0]["local_target_mapping"][0][1] = "tampered"
    with pytest.raises(Task2CandidateAblationV5Error, match="local-ID provenance"):
        validate_task2_candidate_ablation_v5_record(mapping_tamper)

    normalized_tamper = copy.deepcopy(loaded)
    normalized_tamper["calls"][0]["selections"][0]["target_fixture_ids"][0] = (
        "tampered"
    )
    with pytest.raises(Task2CandidateAblationV5Error, match="normalized selections"):
        validate_task2_candidate_ablation_v5_record(normalized_tamper)


@pytest.mark.parametrize("candidate_count", [3, 6, True, 4.0])
def test_only_k4_or_k5_is_accepted(candidate_count):
    value = _value()
    with pytest.raises(Task2CandidateAblationV5Error, match="exactly 4 or 5"):
        discover_task2_candidates_v5(
            ReviewedCandidateProvider(value),  # type: ignore[arg-type]
            value,
            candidate_count=candidate_count,
        )
