"""Focused contracts for gold-blind two-stage Task 2 discovery."""
from __future__ import annotations

import hashlib
import json

import pytest

from memcommit.eval.task2_discovery import (
    build_task2_discovery_input,
    load_task2_discovery_corpus,
)
from memcommit.eval.task2_discovery_v2 import (
    TASK2_DISCOVERY_V2_KIND,
    TASK2_DISCOVERY_V2_PROVIDER_CALLS,
    Task2DiscoveryV2ResponseError,
    Task2StructuralGroup,
    discover_task2_relations_v2,
    run_task2_discovery_v2_campaign,
    score_task2_structure_v2,
)
from memcommit.provider_types import CompletionRun, ProviderIdentity


class SequenceProvider:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []
        self.identity = ProviderIdentity(
            provider="fake",
            model="fixture-model",
            model_digest="a" * 64,
            runtime="pytest",
        )
        self.last_run: CompletionRun | None = None
        self.thinking = "off"

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls.append((prompt, operation, output_schema))
        self.last_run = CompletionRun(
            identity=self.identity,
            operation=operation,
            prompt_tokens=len(prompt.split()),
            completion_tokens=len(self.responses[len(self.calls) - 1].split()),
        )
        return self.responses[len(self.calls) - 1]


def _fixture_to_alias(value) -> dict[str, str]:
    return {
        fixture_id: alias
        for alias, fixture_id in value.alias_to_fixture_id.items()
    }


def _gold_groups(value) -> list[dict[str, object]]:
    aliases = _fixture_to_alias(value)
    return [
        {
            "left_ids": [aliases[item] for item in relation.left_fixture_ids],
            "right_ids": [aliases[item] for item in relation.right_fixture_ids],
        }
        for relation in value.expected
    ]


def test_two_stage_pipeline_is_gold_blind_fixed_and_structurally_exact():
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=3
    )
    gold_groups = _gold_groups(value)
    # The draft deliberately omits most aliases and repeats one candidate.
    stage1_raw = json.dumps({"groups": [gold_groups[0], gold_groups[0]]})
    stage2_raw = json.dumps({"groups": gold_groups})
    provider = SequenceProvider([stage1_raw, stage2_raw])

    run = discover_task2_relations_v2(provider, value)  # type: ignore[arg-type]

    assert len(provider.calls) == run.provider_call_count == TASK2_DISCOVERY_V2_PROVIDER_CALLS == 2
    assert run.contract_valid is True
    assert run.stage1.contract_valid is True
    assert run.stage2.contract_valid is True
    assert len(run.stage1.groups) == 2
    assert run.stage1.groups[0] == run.stage1.groups[1]
    assert run.groups == run.stage2.groups
    assert run.score["exact_structure_groups"] == 3
    assert run.score["member_counterpart_macro_jaccard"] == 1.0
    assert run.score["exact_complete_match"] is True
    assert run.stage1.raw_response == stage1_raw
    assert run.stage2.raw_response == stage2_raw
    assert run.stage1.response_digest == hashlib.sha256(stage1_raw.encode()).hexdigest()
    assert run.stage2.response_digest == hashlib.sha256(stage2_raw.encode()).hexdigest()
    assert run.stage1.elapsed_seconds >= 0.0
    assert run.stage2.elapsed_seconds >= 0.0

    fixture_ids = set(value.alias_to_fixture_id.values())
    all_aliases = set(value.alias_to_fixture_id)
    for prompt, operation, schema in provider.calls:
        assert operation in {
            "task2 structural discovery stage1",
            "task2 structural discovery stage2",
        }
        assert schema is not None
        assert "band" not in prompt.lower()
        assert "band" not in json.dumps(schema).lower()
        assert fixture_ids.isdisjoint(set(prompt.split('"')))
        assert all_aliases <= set(prompt.split('"'))
    assert json.dumps(stage1_raw) in provider.calls[1][0]


def test_stage2_still_runs_when_stage1_uses_an_unknown_alias():
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=2
    )
    valid_group = _gold_groups(value)[0]
    stage1_raw = json.dumps(
        {
            "groups": [
                {"left_ids": ["not-an-input-alias"], "right_ids": valid_group["right_ids"]}
            ]
        }
    )
    stage2_raw = json.dumps({"groups": _gold_groups(value)})
    provider = SequenceProvider([stage1_raw, stage2_raw])

    with pytest.raises(Task2DiscoveryV2ResponseError) as captured:
        discover_task2_relations_v2(provider, value)  # type: ignore[arg-type]

    assert len(provider.calls) == 2
    assert captured.value.run.contract_valid is False
    assert captured.value.run.stage1.contract_valid is False
    assert captured.value.run.stage2.contract_valid is True
    assert captured.value.run.stage1.raw_response == stage1_raw
    assert captured.value.run.stage2.raw_response == stage2_raw
    assert captured.value.run.score["exact_complete_match"] is True


def test_stage2_requires_every_alias_exactly_once_and_retains_both_calls():
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=2
    )
    gold_groups = _gold_groups(value)
    stage1_raw = json.dumps({"groups": []})
    stage2_raw = json.dumps({"groups": gold_groups[:-1]})
    provider = SequenceProvider([stage1_raw, stage2_raw])

    with pytest.raises(Task2DiscoveryV2ResponseError, match="every left and right alias") as captured:
        discover_task2_relations_v2(provider, value)  # type: ignore[arg-type]

    assert len(provider.calls) == 2
    run = captured.value.run
    assert run.stage1.contract_valid is True
    assert run.stage2.contract_valid is False
    assert run.stage1.raw_response == stage1_raw
    assert run.stage2.raw_response == stage2_raw
    assert run.stage1.prompt_digest
    assert run.stage1.schema_digest
    assert run.stage1.response_digest
    assert run.stage2.prompt_digest
    assert run.stage2.schema_digest
    assert run.stage2.response_digest


def test_nm_gold_is_scored_as_a_hypergroup_not_cartesian_pair_labels():
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=18
    )
    predicted = [
        Task2StructuralGroup(relation.left_fixture_ids, relation.right_fixture_ids)
        for relation in value.expected
        if relation.pair_id != "T2-018"
    ]
    nm = next(relation for relation in value.expected if relation.pair_id == "T2-018")
    predicted.extend(
        [
            Task2StructuralGroup(nm.left_fixture_ids[:2], nm.right_fixture_ids[:1]),
            Task2StructuralGroup(nm.left_fixture_ids[2:], nm.right_fixture_ids[1:]),
        ]
    )

    score = score_task2_structure_v2(value, predicted)

    assert score["exact_complete_match"] is False
    assert score["exact_structure_groups"] == 17
    assert 0.0 < score["member_counterpart_macro_jaccard"] < 1.0
    assert not any("pair" in key for key in score)


def test_campaign_validates_lock_and_atomically_retains_a_valid_attempt(tmp_path):
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=26
    )
    stage1_raw = json.dumps({"groups": _gold_groups(value)[:5]})
    stage2_raw = json.dumps({"groups": _gold_groups(value)})
    provider = SequenceProvider([stage1_raw, stage2_raw])

    record = run_task2_discovery_v2_campaign(
        provider,  # type: ignore[arg-type]
        ledger_dir=tmp_path,
        provider_connection_seconds=1.25,
        group_count=26,
    )

    assert len(provider.calls) == 2
    assert record["kind"] == TASK2_DISCOVERY_V2_KIND
    assert record["scorer_version"] == 2
    assert record["status"] == "VALID"
    assert record["contract_valid"] is True
    assert record["provider"] == {
        "provider": "fake",
        "model": "fixture-model",
        "model_digest": "a" * 64,
        "runtime": "pytest",
        "endpoint": None,
        "reasoning_effort": None,
    }
    assert record["provider_run"]["operation"] == "task2 structural discovery stage2"  # type: ignore[index]
    assert record["lock"]["corpus_locked"] is True  # type: ignore[index]
    assert record["lock"]["slice_locked"] is True  # type: ignore[index]
    assert record["lock"]["selected_slice"]["group_count"] == 26  # type: ignore[index]
    assert record["corpus"]["selected_left_count"] == 29  # type: ignore[index]
    assert record["corpus"]["selected_right_count"] == 27  # type: ignore[index]
    assert record["corpus"]["input_digest"] == value.input_digest  # type: ignore[index]
    assert record["corpus"]["alias_mapping_digest"] == value.alias_mapping_digest  # type: ignore[index]
    assert record["stage1"]["raw_response"] == stage1_raw  # type: ignore[index]
    assert record["stage2"]["raw_response"] == stage2_raw  # type: ignore[index]
    assert record["score"]["exact_complete_match"] is True  # type: ignore[index]
    assert record["timing"]["provider_connection_seconds"] == 1.25  # type: ignore[index]
    assert record["timing"]["total_seconds"] >= 1.25  # type: ignore[index]
    assert all("band" not in item for item in record["expected_groups"])  # type: ignore[union-attr]

    path = tmp_path / "task2-discovery-v2" / (
        f"{record['run_id']}-fake.json"
    )
    assert record["ledger_path"] == str(path)
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["status"] == "VALID"
    assert persisted["stage1"]["response_digest"] == record["stage1"]["response_digest"]  # type: ignore[index]
    assert persisted["stage2"]["response_digest"] == record["stage2"]["response_digest"]  # type: ignore[index]


def test_campaign_retains_invalid_output_instead_of_losing_exception_run(tmp_path):
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=26
    )
    gold_groups = _gold_groups(value)
    stage1_raw = json.dumps(
        {
            "groups": [
                {
                    "left_ids": ["unknown-alias"],
                    "right_ids": gold_groups[0]["right_ids"],
                }
            ]
        }
    )
    stage2_raw = json.dumps({"groups": gold_groups})
    provider = SequenceProvider([stage1_raw, stage2_raw])

    record = run_task2_discovery_v2_campaign(
        provider,  # type: ignore[arg-type]
        ledger_dir=tmp_path,
        provider_connection_seconds=0.5,
        group_count=26,
    )

    assert len(provider.calls) == 2
    assert record["status"] == "INVALID_OUTPUT"
    assert record["contract_valid"] is False
    assert "invalid candidate group" in record["validation_error"]  # type: ignore[operator]
    assert record["stage1"]["contract_valid"] is False  # type: ignore[index]
    assert record["stage2"]["contract_valid"] is True  # type: ignore[index]
    assert record["stage1"]["raw_response"] == stage1_raw  # type: ignore[index]
    assert record["stage2"]["raw_response"] == stage2_raw  # type: ignore[index]
    assert record["score"]["exact_complete_match"] is True  # type: ignore[index]
    path = tmp_path / "task2-discovery-v2" / f"{record['run_id']}-fake.json"
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["status"] == "INVALID_OUTPUT"
    assert persisted["validation_error"] == record["validation_error"]
