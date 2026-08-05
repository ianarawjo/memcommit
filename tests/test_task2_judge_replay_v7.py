"""Contracts for the canonical evidence-first Task 2 V7 judge replay."""

from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path

import pytest

import memcommit.eval.task2_judge_replay_v5 as judge_v5
import memcommit.eval.task2_judge_replay_v6 as judge_v6
import memcommit.eval.task2_judge_replay_v7 as judge_v7
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
    """Produce distinct, contract-valid parents without changing the Gold edge."""

    def __init__(self, value, *, reverse_fillers: bool) -> None:
        self.identity = ProviderIdentity(
            provider=("v7-parent-reverse" if reverse_fillers else "v7-parent-forward"),
            model="fixture-teacher",
            model_digest=("9" if reverse_fillers else "8") * 64,
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
                    target["id"] for target in targets if target["id"] not in selected
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


_EVIDENCE_BY_LABEL = {
    "NEAR_DUPLICATE": (
        "SAME_STANDALONE_CLAIM",
        "ALIGNED",
        "SAME_CONTEXT",
        "PEER",
    ),
    "SAME_PRINCIPLE": (
        "SAME_GOVERNING_PRINCIPLE",
        "ALIGNED",
        "SAME_CONTEXT",
        "PEER",
    ),
    "CONTEXT_VARIANT": (
        "SAME_PRIMARY_DECISION_OR_REVIEW_UNIT",
        "ALIGNED",
        "MATERIAL_CONTEXT_DIFFERENCE",
        "PEER",
    ),
    "CONFLICT": (
        "SAME_PRIMARY_DECISION_OR_REVIEW_UNIT",
        "INCOMPATIBLE",
        "SAME_CONTEXT",
        "PEER",
    ),
    "COMPLEMENT_OR_JOINT_PART": (
        "SAME_PRIMARY_DECISION_OR_REVIEW_UNIT",
        "COMPLEMENTARY",
        "MATERIAL_CONTEXT_DIFFERENCE",
        "WHOLE_PART_OR_JOINT",
    ),
    "UNRELATED": (
        "TOPIC_ONLY_DIFFERENT_UNIT",
        "NOT_APPLICABLE",
        "NOT_APPLICABLE",
        "NOT_APPLICABLE",
    ),
}


class EvidenceTeacher:
    """Return exact decomposed evidence from text, never fixture or Gold IDs."""

    def __init__(
        self,
        value,
        *,
        fail_at: int | None = None,
        abstain_first: bool = False,
        impossible_first: bool = False,
        alternate_context_evidence: bool = False,
    ) -> None:
        self.identity = ProviderIdentity(
            provider="v7-evidence-teacher",
            model="fixture-teacher",
            model_digest="a" * 64,
            runtime="pytest",
        )
        self.thinking = "off"
        self.last_run: CompletionRun | None = None
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []
        self.fail_at = fail_at
        self.abstain_first = abstain_first
        self.impossible_first = impossible_first
        self.alternate_context_evidence = alternate_context_evidence
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
        payload = json.loads(prompt.split(judge_v7._PAYLOAD_MARKER, 1)[1])
        result = []
        for pair_index, pair in enumerate(payload["pairs"]):
            left = self.fixture_by_text[
                (pair["left"]["topic"], pair["left"]["content"])
            ]
            right = self.fixture_by_text[
                (pair["right"]["topic"], pair["right"]["content"])
            ]
            counterparts, expected_label = self.expected[left]
            label = expected_label if right in counterparts else "UNRELATED"
            anchor, polarity, context, composition = _EVIDENCE_BY_LABEL[label]
            if label == "CONTEXT_VARIANT" and self.alternate_context_evidence:
                anchor = "SAME_GOVERNING_PRINCIPLE"
            item = {
                "pair_id": pair["pair_id"],
                "resolution": "RESOLVED",
                "semantic_anchor": anchor,
                "polarity": polarity,
                "context_relation": context,
                "composition": composition,
            }
            if call_index == 0 and pair_index == 0 and self.abstain_first:
                item.update(
                    {
                        "resolution": "UNRESOLVED",
                        "semantic_anchor": "UNDETERMINED",
                        "polarity": "NOT_APPLICABLE",
                        "context_relation": "NOT_APPLICABLE",
                        "composition": "NOT_APPLICABLE",
                    }
                )
            if call_index == 0 and pair_index == 0 and self.impossible_first:
                item.update(
                    {
                        "semantic_anchor": "TOPIC_ONLY_DIFFERENT_UNIT",
                        "polarity": "INCOMPATIBLE",
                        "context_relation": "SAME_CONTEXT",
                        "composition": "PEER",
                    }
                )
            result.append(item)
        response = json.dumps({"evidence": result})
        self.last_run = CompletionRun(
            identity=self.identity,
            operation=operation,
            prompt_tokens=len(prompt.split()),
            completion_tokens=len(response.split()),
        )
        return response


@pytest.fixture(scope="module")
def parent_records(tmp_path_factory):
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=26
    )
    ledger_dir = tmp_path_factory.mktemp("task2-judge-v7-parents")
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


def _canonical_key(pair):
    return (
        (pair.source_fixture_id, pair.target_fixture_id)
        if pair.direction == judge_v5.LEFT_TO_RIGHT
        else (pair.target_fixture_id, pair.source_fixture_id)
    )


def test_canonical_count_order_map_and_schedule_are_frozen(parent_records):
    value, records = parent_records
    forward = judge_v7.build_task2_judge_replay_v7_input(records)
    reverse = judge_v7.build_task2_judge_replay_v7_input(list(reversed(records)))
    baseline = forward.v5_input
    expected_keys = {_canonical_key(pair) for pair in baseline.candidate_pairs}

    assert len(forward.canonical_pairs) == len(expected_keys)
    assert len(forward.canonical_pairs) < len(baseline.candidate_pairs)
    assert {
        (pair.left_fixture_id, pair.right_fixture_id)
        for pair in forward.canonical_pairs
    } == expected_keys
    assert forward == reverse
    assert (
        tuple(mapping.canonical_pair for mapping in forward.canonical_to_directed)
        == forward.canonical_pairs
    )
    assert {
        directed
        for mapping in forward.canonical_to_directed
        for directed in mapping.directed_pairs
    } == set(baseline.candidate_pairs)
    assert all(
        len(mapping.directed_pairs) in (1, 2)
        for mapping in forward.canonical_to_directed
    )
    assert forward.canonical_pairs != tuple(
        sorted(
            forward.canonical_pairs,
            key=lambda pair: (pair.left_fixture_id, pair.right_fixture_id),
        )
    )
    assert judge_v7.task2_judge_replay_v7_provider_call_count(forward) == math.ceil(
        len(expected_keys) / 24
    )

    # Gold and parent metadata bind the retained experiment but must never salt
    # provider-visible order or call boundaries.
    metadata_poisoned = replace(
        baseline,
        gold_relations_digest="f" * 64,
        replay_freeze_digest="e" * 64,
        parent_ledgers=tuple(reversed(baseline.parent_ledgers)),
    )
    poisoned_pairs, poisoned_map = judge_v7._canonicalize(metadata_poisoned)
    assert poisoned_pairs == forward.canonical_pairs
    assert poisoned_map == forward.canonical_to_directed

    first = EvidenceTeacher(value)
    second = EvidenceTeacher(value)
    judge_v7.judge_task2_candidate_union_v7(first, forward)  # type: ignore[arg-type]
    judge_v7.judge_task2_candidate_union_v7(second, reverse)  # type: ignore[arg-type]
    assert [call[0] for call in first.calls] == [call[0] for call in second.calls]
    for prompt, _operation, _schema in first.calls:
        payload = json.loads(prompt.split(judge_v7._PAYLOAD_MARKER, 1)[1])
        assert all(
            set(pair) == {"pair_id", "left", "right"} for pair in payload["pairs"]
        )
        assert all(
            pair["pair_id"] == f"p{index:02d}"
            for index, pair in enumerate(payload["pairs"], start=1)
        )


@pytest.mark.parametrize(
    ("evidence", "expected"),
    [
        (
            ("RESOLVED", "SAME_STANDALONE_CLAIM", "ALIGNED", "SAME_CONTEXT", "PEER"),
            "NEAR_DUPLICATE",
        ),
        (
            ("RESOLVED", "SAME_GOVERNING_PRINCIPLE", "ALIGNED", "SAME_CONTEXT", "PEER"),
            "SAME_PRINCIPLE",
        ),
        (
            (
                "RESOLVED",
                "SAME_PRIMARY_DECISION_OR_REVIEW_UNIT",
                "ALIGNED",
                "MATERIAL_CONTEXT_DIFFERENCE",
                "PEER",
            ),
            "CONTEXT_VARIANT",
        ),
        (
            (
                "RESOLVED",
                "SAME_PRIMARY_DECISION_OR_REVIEW_UNIT",
                "INCOMPATIBLE",
                "SAME_CONTEXT",
                "PEER",
            ),
            "CONFLICT",
        ),
        (
            (
                "RESOLVED",
                "SAME_PRIMARY_DECISION_OR_REVIEW_UNIT",
                "COMPLEMENTARY",
                "MATERIAL_CONTEXT_DIFFERENCE",
                "WHOLE_PART_OR_JOINT",
            ),
            "COMPLEMENT_OR_JOINT_PART",
        ),
        (
            (
                "RESOLVED",
                "TOPIC_ONLY_DIFFERENT_UNIT",
                "NOT_APPLICABLE",
                "NOT_APPLICABLE",
                "NOT_APPLICABLE",
            ),
            "UNRELATED",
        ),
        (
            (
                "UNRESOLVED",
                "UNDETERMINED",
                "NOT_APPLICABLE",
                "NOT_APPLICABLE",
                "NOT_APPLICABLE",
            ),
            "ABSTAIN",
        ),
    ],
)
def test_projection_table(evidence, expected):
    assert (
        judge_v7.project_task2_evidence_v7(
            resolution=evidence[0],
            semantic_anchor=evidence[1],
            polarity=evidence[2],
            context_relation=evidence[3],
            composition=evidence[4],
        )
        == expected
    )


def test_projection_table_includes_same_principle_context_and_same_context_joint():
    assert (
        judge_v7.project_task2_evidence_v7(
            resolution="RESOLVED",
            semantic_anchor="SAME_GOVERNING_PRINCIPLE",
            polarity="ALIGNED",
            context_relation="MATERIAL_CONTEXT_DIFFERENCE",
            composition="PEER",
        )
        == "CONTEXT_VARIANT"
    )
    assert (
        judge_v7.project_task2_evidence_v7(
            resolution="RESOLVED",
            semantic_anchor="SAME_PRIMARY_DECISION_OR_REVIEW_UNIT",
            polarity="COMPLEMENTARY",
            context_relation="SAME_CONTEXT",
            composition="WHOLE_PART_OR_JOINT",
        )
        == "COMPLEMENT_OR_JOINT_PART"
    )
    assert len(judge_v7._PROJECTION_TABLE) == 9


@pytest.mark.parametrize(
    "evidence",
    [
        ("UNRESOLVED", "SAME_STANDALONE_CLAIM", "ALIGNED", "SAME_CONTEXT", "PEER"),
        (
            "RESOLVED",
            "TOPIC_ONLY_DIFFERENT_UNIT",
            "INCOMPATIBLE",
            "SAME_CONTEXT",
            "PEER",
        ),
        (
            "RESOLVED",
            "SAME_PRIMARY_DECISION_OR_REVIEW_UNIT",
            "COMPLEMENTARY",
            "SAME_CONTEXT",
            "PEER",
        ),
        (
            "RESOLVED",
            "SAME_GOVERNING_PRINCIPLE",
            "INCOMPATIBLE",
            "MATERIAL_CONTEXT_DIFFERENCE",
            "WHOLE_PART_OR_JOINT",
        ),
    ],
)
def test_impossible_projection_combinations_fail_closed(evidence):
    with pytest.raises(judge_v7.Task2EvidenceProjectionError):
        judge_v7.project_task2_evidence_v7(
            resolution=evidence[0],
            semantic_anchor=evidence[1],
            polarity=evidence[2],
            context_relation=evidence[3],
            composition=evidence[4],
        )


def test_exact_teacher_projects_once_to_all_directions_and_scores_v5(parent_records):
    value, records = parent_records
    replay_input = judge_v7.build_task2_judge_replay_v7_input(records)
    provider = EvidenceTeacher(value)
    run = judge_v7.judge_task2_candidate_union_v7(
        provider,
        replay_input,  # type: ignore[arg-type]
    )

    assert run.contract_valid
    assert len(run.evidence) == len(replay_input.canonical_pairs)
    assert len(run.projected_decisions) == len(replay_input.v5_input.candidate_pairs)
    canonical_score = run.score["canonical_judge"]
    directed_score = run.score["projected_directed_v5"]
    assert canonical_score["binary_same_hypergroup"]["accuracy"] == 1.0
    assert canonical_score["group_induced_enum"]["exact_accuracy"] == 1.0
    assert directed_score["binary_same_hypergroup"]["accuracy"] == 1.0
    assert directed_score["group_induced_enum"]["exact_accuracy"] == 1.0
    assert directed_score["source_accepted_set"]["exact_accuracy"] == 1.0
    canonical = run.score["canonical_evidence"]
    assert canonical["resolved"] == len(replay_input.canonical_pairs)
    assert canonical["explicit_abstain"] == 0
    assert canonical["missing_due_invalid_call"] == 0
    invariance = run.score["direction_invariance"]
    bidirectional = sum(
        len(mapping.directed_pairs) == 2
        for mapping in replay_input.canonical_to_directed
    )
    assert invariance["bidirectional_canonical_pairs"] == bidirectional
    assert invariance["comparable_resolved_bidirectional_pairs"] == bidirectional
    assert invariance["invariant_resolved_bidirectional_pairs"] == bidirectional
    assert invariance["invariance_rate"] == 1.0
    assert invariance["partially_projected_bidirectional_pairs"] == 0
    assert all(
        len(payload[0].split(judge_v7._PAYLOAD_MARKER)) == 2
        for payload in provider.calls
    )
    assert all("final relationship label" in payload[0] for payload in provider.calls)
    assert all(
        label not in provider.calls[0][0] for label in judge_v5.TASK2_JUDGE_LABELS
    )

    multi_left: set[str] = set()
    multi_right: set[str] = set()
    for relation in value.expected:
        if len(relation.left_fixture_ids) > 1 or len(relation.right_fixture_ids) > 1:
            multi_left.update(relation.left_fixture_ids)
            multi_right.update(relation.right_fixture_ids)
    expected_multi_scope = sum(
        pair.left_fixture_id in multi_left or pair.right_fixture_id in multi_right
        for pair in replay_input.canonical_pairs
    )
    assert any(
        pair.left_fixture_id not in multi_left and pair.right_fixture_id in multi_right
        for pair in replay_input.canonical_pairs
    )
    assert canonical_score["multi_member_binary"]["total"] == expected_multi_scope


def test_unresolved_is_contract_valid_retained_abstain_and_v5_missing(parent_records):
    value, records = parent_records
    replay_input = judge_v7.build_task2_judge_replay_v7_input(records)
    run = judge_v7.judge_task2_candidate_union_v7(
        EvidenceTeacher(value, abstain_first=True),  # type: ignore[arg-type]
        replay_input,
    )

    assert run.contract_valid
    assert len(run.evidence) == len(replay_input.canonical_pairs)
    assert run.evidence[0].projected_label == judge_v7.TASK2_ABSTAIN
    assert run.score["canonical_evidence"]["explicit_abstain"] == 1
    assert run.score["canonical_evidence"]["missing_due_invalid_call"] == 0
    first_map = replay_input.canonical_to_directed[0]
    projected_keys = {
        (item.direction, item.source_fixture_id, item.target_fixture_id)
        for item in run.projected_decisions
    }
    assert all(
        (item.direction, item.source_fixture_id, item.target_fixture_id)
        not in projected_keys
        for item in first_map.directed_pairs
    )
    missing = (
        run.score["projected_directed_v5"]["binary_same_hypergroup"]["missing_positive"]
        + run.score["projected_directed_v5"]["binary_same_hypergroup"][
            "missing_negative"
        ]
    )
    assert missing == len(first_map.directed_pairs)
    canonical_binary = run.score["canonical_judge"]["binary_same_hypergroup"]
    assert (
        canonical_binary["explicit_abstain_positive"]
        + canonical_binary["explicit_abstain_negative"]
        == 1
    )
    assert canonical_binary["invalid_call_missing_positive"] == 0
    assert canonical_binary["invalid_call_missing_negative"] == 0


def test_impossible_provider_evidence_invalidates_call_without_repair(parent_records):
    value, records = parent_records
    replay_input = judge_v7.build_task2_judge_replay_v7_input(records)
    with pytest.raises(judge_v7.Task2JudgeReplayV7ResponseError) as caught:
        judge_v7.judge_task2_candidate_union_v7(
            EvidenceTeacher(value, impossible_first=True),  # type: ignore[arg-type]
            replay_input,
        )
    run = caught.value.run
    assert run.provider_call_count == run.expected_provider_call_count
    assert not run.calls[0].response_contract_valid
    assert run.calls[0].evidence == ()
    assert run.calls[0].projected_decisions == ()
    assert "contradictory or unsupported" in run.calls[0].validation_error
    assert run.score["canonical_evidence"]["missing_due_invalid_call"] == (
        run.calls[0].pair_count
    )


def test_response_order_normalizes_by_id_and_bad_coverage_fails_closed():
    directed = (judge_v5.Task2JudgeCandidatePair("LEFT_TO_RIGHT", "L1", "R1"),)
    mapping = {
        "p01": (judge_v7.Task2CanonicalPair("L1", "R1"), directed),
        "p02": (
            judge_v7.Task2CanonicalPair("L2", "R2"),
            (judge_v5.Task2JudgeCandidatePair("LEFT_TO_RIGHT", "L2", "R2"),),
        ),
    }

    def unrelated(pair_id):
        return {
            "pair_id": pair_id,
            "resolution": "RESOLVED",
            "semantic_anchor": "TOPIC_ONLY_DIFFERENT_UNIT",
            "polarity": "NOT_APPLICABLE",
            "context_relation": "NOT_APPLICABLE",
            "composition": "NOT_APPLICABLE",
        }

    raw = json.dumps({"evidence": [unrelated("p02"), unrelated("p01")]})
    evidence, decisions, valid, category, error = judge_v7._parse_response(
        raw_response=raw,
        provider_error_type=None,
        pair_by_local_id=mapping,
    )
    assert valid and category is None and error is None
    assert [(item.left_fixture_id, item.right_fixture_id) for item in evidence] == [
        ("L1", "R1"),
        ("L2", "R2"),
    ]
    assert len(decisions) == 2

    duplicate_id = json.dumps({"evidence": [unrelated("p01"), unrelated("p01")]})
    missing_id = json.dumps({"evidence": [unrelated("p01")]})
    extra_label = unrelated("p01") | {"label": "UNRELATED"}
    extra_field = json.dumps({"evidence": [extra_label, unrelated("p02")]})
    duplicate_key = (
        '{"evidence":[{"pair_id":"p01","pair_id":"p02",'
        '"resolution":"RESOLVED","semantic_anchor":'
        '"TOPIC_ONLY_DIFFERENT_UNIT","polarity":"NOT_APPLICABLE",'
        '"context_relation":"NOT_APPLICABLE","composition":'
        '"NOT_APPLICABLE"}]}'
    )
    for invalid in (duplicate_id, missing_id, extra_field, duplicate_key):
        parsed = judge_v7._parse_response(
            raw_response=invalid,
            provider_error_type=None,
            pair_by_local_id=mapping,
        )
        assert parsed[2] is False
        assert parsed[0] == () and parsed[1] == ()


def test_provider_failure_continues_fixed_schedule(parent_records):
    value, records = parent_records
    replay_input = judge_v7.build_task2_judge_replay_v7_input(records)
    provider = EvidenceTeacher(value, fail_at=0)
    with pytest.raises(judge_v7.Task2JudgeReplayV7ResponseError) as caught:
        judge_v7.judge_task2_candidate_union_v7(
            provider,  # type: ignore[arg-type]
            replay_input,
            known_error_types=(TimeoutError,),
        )
    run = caught.value.run
    assert len(provider.calls) == run.expected_provider_call_count
    assert run.provider_call_count == run.expected_provider_call_count
    assert run.calls[0].failure_category == "PROVIDER"
    assert run.calls[0].error_type == "TimeoutError"
    assert "private provider endpoint" not in (run.validation_error or "")
    assert all(call.response_contract_valid for call in run.calls[1:])
    assert run.score["canonical_evidence"]["missing_due_invalid_call"] == (
        run.calls[0].pair_count
    )


def test_campaign_retains_raw_evidence_map_digests_timing_and_final_only(
    parent_records, tmp_path
):
    value, records = parent_records
    provider = EvidenceTeacher(value)
    provider.thinking = False
    record = judge_v7.run_task2_judge_replay_v7_campaign(
        provider,  # type: ignore[arg-type]
        parent_ledgers=records,
        ledger_dir=tmp_path,
        provider_connection_seconds=0.125,
    )
    path = Path(record["ledger_path"])
    assert record["contract_valid"] is True
    assert record["effective_thinking"] is False
    assert record["durability"]["mode"] == "FINAL_ONLY"
    assert record["evidence_protocol"]["provider_returns_final_enum"] is False
    assert record["evaluation_boundary"] == {
        "role": "JUDGE_ABLATION_ONLY",
        "component_reconciliation": False,
        "group_band_classification": False,
        "scale_promotion_eligible": False,
        "reason": (
            "CANONICAL_PAIR_EVIDENCE_IS_NOT_A_GROUP_RECOVERY_OR_"
            "COMPONENT_RECONCILIATION_STAGE"
        ),
    }
    assert record["canonical_bundle"]["canonical_to_directed"]
    assert len(record["canonical_bundle"]["digest"]) == 64
    assert len(record["canonical_bundle"]["canonical_to_directed_digest"]) == 64
    assert len(record["canonical_bundle"]["evidence_freeze_digest"]) == 64
    assert all(call["raw_response"] for call in record["calls"])
    assert all(call["evidence"] for call in record["calls"])
    assert record["evidence_judgments"]
    assert record["projected_decisions"]
    assert record["timing"]["provider_connection_seconds"] == 0.125
    assert record["timing"]["total_seconds"] >= 0.125
    assert json.loads(path.read_text(encoding="utf-8")) == record
    assert judge_v7.validate_task2_judge_replay_v7_record(record)["valid"] is True


def test_campaign_rejects_malformed_provider_identity_before_any_call(
    parent_records, tmp_path
):
    value, records = parent_records
    provider = EvidenceTeacher(value)
    provider.identity = ProviderIdentity(provider="", model="")
    with pytest.raises(judge_v7.Task2JudgeReplayV7Error):
        judge_v7.run_task2_judge_replay_v7_campaign(
            provider,  # type: ignore[arg-type]
            parent_ledgers=records,
            ledger_dir=tmp_path,
            provider_connection_seconds=0.0,
        )
    assert provider.calls == []


def test_strict_record_validator_and_literal_evidence_comparator(
    parent_records, tmp_path
):
    value, records = parent_records
    exact = judge_v7.run_task2_judge_replay_v7_campaign(
        EvidenceTeacher(value),  # type: ignore[arg-type]
        parent_ledgers=records,
        ledger_dir=tmp_path / "exact",
        provider_connection_seconds=0.0,
    )
    abstained = judge_v7.run_task2_judge_replay_v7_campaign(
        EvidenceTeacher(value, abstain_first=True),  # type: ignore[arg-type]
        parent_ledgers=records,
        ledger_dir=tmp_path / "abstained",
        provider_connection_seconds=0.0,
    )
    same_projection = judge_v7.run_task2_judge_replay_v7_campaign(
        EvidenceTeacher(value, alternate_context_evidence=True),  # type: ignore[arg-type]
        parent_ledgers=records,
        ledger_dir=tmp_path / "same-projection",
        provider_connection_seconds=0.0,
    )
    validation = judge_v7.validate_task2_judge_replay_v7_record(exact)
    assert validation["valid"] is True
    assert validation["canonical_pair_count"] == exact["canonical_bundle"]["pair_count"]
    comparison = judge_v7.compare_task2_judge_replay_v7_records(exact, abstained)
    total = comparison["canonical_pair_count"]
    assert comparison["fixed_call_inputs_identical"] is True
    assert comparison["first"]["run_id"] == exact["run_id"]
    assert comparison["second"]["run_id"] == abstained["run_id"]
    assert comparison["literal_evidence_vector_agreement"]["exact"] == total - 1
    assert comparison["per_field_agreement"]["projected_label"]["exact"] == total - 1
    assert comparison["binary_accept_reject_abstain_agreement"]["exact"] == total - 1
    assert comparison["abstention"]["first"] == 0
    assert comparison["abstention"]["second"] == 1
    assert comparison["parity_gate"]["passed"] is False
    assert comparison["source_accepted_set_agreement"]["total"] > 0
    assert comparison["multi_member_agreement"]["literal_evidence_vector"]["total"] > 0

    decomposition = judge_v7.compare_task2_judge_replay_v7_records(
        exact, same_projection
    )
    assert decomposition["literal_evidence_vector_agreement"]["exact"] < total
    assert decomposition["per_field_agreement"]["projected_label"]["exact"] == total
    assert decomposition["binary_accept_reject_abstain_agreement"]["exact"] == total
    assert (
        decomposition["source_accepted_set_agreement"]["exact"]
        == (decomposition["source_accepted_set_agreement"]["total"])
    )

    with pytest.raises(judge_v7.Task2JudgeReplayV7Error):
        judge_v7.compare_task2_judge_replay_v7_records(exact, exact)

    mutations = []
    projection_digest = copy.deepcopy(exact)
    projection_digest["evidence_protocol"]["projection_protocol_digest"] = "0" * 64
    mutations.append(("projection digest", projection_digest))
    schema_digest = copy.deepcopy(exact)
    schema_digest["evidence_protocol"]["schema_protocol_digest"] = "0" * 64
    mutations.append(("schema digest", schema_digest))
    projected = copy.deepcopy(exact)
    projected["projected_decisions"][0]["label"] = (
        "NEAR_DUPLICATE"
        if projected["projected_decisions"][0]["label"] == "UNRELATED"
        else "UNRELATED"
    )
    mutations.append(("top projected decision", projected))
    raw = copy.deepcopy(exact)
    raw_payload = json.loads(raw["calls"][0]["raw_response"])
    raw_payload["evidence"][0]["composition"] = (
        "NOT_APPLICABLE"
        if raw_payload["evidence"][0]["composition"] == "PEER"
        else "PEER"
    )
    raw["calls"][0]["raw_response"] = json.dumps(raw_payload)
    raw["calls"][0]["response_digest"] = hashlib.sha256(
        raw["calls"][0]["raw_response"].encode()
    ).hexdigest()
    mutations.append(("raw evidence", raw))
    call_run = copy.deepcopy(exact)
    call_run["calls"][0]["provider_run"]["operation"] = "other-operation"
    mutations.append(("call completion", call_run))
    top_run = copy.deepcopy(exact)
    top_run["provider_run"]["identity"]["model"] = "other-model"
    mutations.append(("top completion", top_run))
    for label, mutation in mutations:
        try:
            judge_v7.validate_task2_judge_replay_v7_record(mutation)
        except judge_v7.Task2JudgeReplayV7Error:
            continue
        pytest.fail(f"strict validator accepted mutation: {label}")


def test_frozen_input_tampering_is_rejected(parent_records):
    _value, records = parent_records
    replay_input = judge_v7.build_task2_judge_replay_v7_input(records)
    mutated_first = replace(
        replay_input.canonical_pairs[0], left_fixture_id="not-a-left-fixture"
    )
    mutated = replace(
        replay_input,
        canonical_pairs=(mutated_first, *replay_input.canonical_pairs[1:]),
    )
    with pytest.raises(judge_v7.Task2JudgeReplayV7Error):
        judge_v7.judge_task2_candidate_union_v7(
            EvidenceTeacher(_value),
            mutated,  # type: ignore[arg-type]
        )


def test_v5_and_v6_prompts_remain_byte_pinned_while_v7_returns_only_evidence():
    v5_pairs = [
        {
            "pair_id": "p01",
            "source": {"topic": "t", "content": "a"},
            "target": {"topic": "t", "content": "b"},
        }
    ]
    v7_pairs = [
        {
            "pair_id": "p01",
            "left": {"topic": "t", "content": "a"},
            "right": {"topic": "t", "content": "b"},
        }
    ]
    assert hashlib.sha256(judge_v5._prompt(v5_pairs).encode()).hexdigest() == (
        "a05da28af356c84a34a1f27ba343984eb08d2d8f936b534ad32c91b5ebc12194"
    )
    assert hashlib.sha256(judge_v6._prompt(v5_pairs).encode()).hexdigest() == (
        "41b7cd602287b46f6f1b36d14f41d953afa7cb3a3dfae7dee4848acb972ed8ad"
    )
    prompt = judge_v7._prompt(v7_pairs)
    schema = judge_v7._schema(("p01",))
    assert "Do not return or invent a final relationship label" in prompt
    assert "shared vocabulary" in prompt
    assert "Adjacent usefulness" in prompt
    assert "Generic compatibility" in prompt
    assert "genuine conflict" in prompt
    assert "genuine joint part" in prompt
    assert "Whole-part-or-joint composition takes precedence" in prompt
    assert "label" not in schema["properties"]["evidence"]["items"]["properties"]
    assert all(label not in prompt for label in judge_v5.TASK2_JUDGE_LABELS)
