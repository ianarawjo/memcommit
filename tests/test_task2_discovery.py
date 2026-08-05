"""Contracts for Task 2 relation discovery and provider parity scoring."""
from __future__ import annotations

from collections import Counter
import json

import pytest

from memcommit.eval.task2_discovery import (
    DEFAULT_TASK2_GROUP_SLICE,
    TASK2_RELATION_BANDS,
    Task2DiscoveryError,
    build_task2_discovery_input,
    compare_task2_discovery_records,
    discover_task2_relations,
    load_task2_discovery_corpus,
    run_task2_discovery_campaign,
    score_task2_discovery,
)
from memcommit.provider_types import CompletionRun, ProviderIdentity


class FakeProvider:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls.append((prompt, operation, output_schema))
        return self.response


class CampaignProvider(FakeProvider):
    def __init__(self, response: str) -> None:
        super().__init__(response)
        self.identity = ProviderIdentity(
            provider="ollama",
            model="qwen3.6:35b-a3b",
            model_digest="a" * 64,
            runtime="ollama/test",
        )
        self.thinking = False
        self.last_run: CompletionRun | None = None

    def complete(self, prompt, *, operation, output_schema=None):
        response = super().complete(
            prompt,
            operation=operation,
            output_schema=output_schema,
        )
        self.last_run = CompletionRun(
            identity=self.identity,
            operation=operation,
            prompt_tokens=10,
            completion_tokens=10,
        )
        return response


class ExpectedProviderFailure(RuntimeError):
    pass


class RaisingCampaignProvider(CampaignProvider):
    def complete(self, prompt, *, operation, output_schema=None):
        raise ExpectedProviderFailure("sensitive upstream diagnostic")


def _gold_response(value) -> dict[str, object]:
    fixture_to_alias = {
        fixture_id: alias
        for alias, fixture_id in value.alias_to_fixture_id.items()
    }
    return {
        "relations": [
            {
                "left_ids": [
                    fixture_to_alias[fixture_id]
                    for fixture_id in relation.left_fixture_ids
                ],
                "right_ids": [
                    fixture_to_alias[fixture_id]
                    for fixture_id in relation.right_fixture_ids
                ],
                "band": relation.band,
            }
            for relation in value.expected
        ]
    }


def test_full_corpus_is_the_reviewed_exhaustive_150_by_150_partition():
    corpus = load_task2_discovery_corpus(language="en")

    assert len(corpus.left) == 150
    assert len(corpus.right) == 150
    assert len(corpus.relations) == 138
    assert Counter(relation.band for relation in corpus.relations) == {
        "Near Duplicate": 64,
        "Same-Principle Variant": 26,
        "Context-Dependent Variant": 38,
        "Conflict": 8,
        "Compatible Complement": 2,
    }

    partitioned_left = [
        fixture_id
        for relation in corpus.relations
        for fixture_id in relation.left_fixture_ids
    ]
    partitioned_right = [
        fixture_id
        for relation in corpus.relations
        for fixture_id in relation.right_fixture_ids
    ]
    corpus_left = {memory.fixture_id for memory in corpus.left}
    corpus_right = {memory.fixture_id for memory in corpus.right}

    assert len(partitioned_left) == len(set(partitioned_left)) == 150
    assert len(partitioned_right) == len(set(partitioned_right)) == 150
    assert set(partitioned_left) == corpus_left
    assert set(partitioned_right) == corpus_right


def test_default_slice_uses_unrelated_opaque_aliases_and_all_relation_bands():
    corpus = load_task2_discovery_corpus(language="en")
    value = build_task2_discovery_input(corpus)

    assert value.group_count == DEFAULT_TASK2_GROUP_SLICE == 26
    assert len(value.expected) == 26
    assert len(value.left_items) == 29
    assert len(value.right_items) == 27
    assert {relation.band for relation in value.expected} == set(TASK2_RELATION_BANDS)

    left_aliases = {item["id"] for item in value.left_items}
    right_aliases = {item["id"] for item in value.right_items}
    assert left_aliases.isdisjoint(right_aliases)
    assert set(value.alias_to_fixture_id) == left_aliases | right_aliases
    assert all(
        len(alias) == 13 and alias.startswith("a")
        for alias in left_aliases
    )
    assert all(
        len(alias) == 13 and alias.startswith("b")
        for alias in right_aliases
    )
    assert all(
        fixture_id not in alias
        for alias, fixture_id in value.alias_to_fixture_id.items()
    )

    fixture_to_alias = {
        fixture_id: alias
        for alias, fixture_id in value.alias_to_fixture_id.items()
    }
    assert all(
        fixture_to_alias[left_id][1:] != fixture_to_alias[right_id][1:]
        for relation in value.expected
        for left_id in relation.left_fixture_ids
        for right_id in relation.right_fixture_ids
    )


def test_fake_provider_can_discover_exact_gold_and_receives_no_fixture_ids():
    corpus = load_task2_discovery_corpus(language="en")
    value = build_task2_discovery_input(corpus)
    raw = json.dumps(_gold_response(value), ensure_ascii=False)
    provider = FakeProvider(raw)

    run = discover_task2_relations(provider, value)  # type: ignore[arg-type]
    score = score_task2_discovery(value, run.relations)

    assert score["expected_groups"] == score["predicted_groups"] == 26
    assert score["exact_structure_groups"] == score["exact_band_groups"] == 26
    assert score["member_counterpart_exact"] == score["member_counterpart_total"] == 56
    for metric in (
        "group_structure_precision",
        "group_structure_recall",
        "group_band_accuracy",
        "band_accuracy_on_exact_structures",
        "member_counterpart_exact_accuracy",
        "member_counterpart_macro_jaccard",
        "coassignment_precision",
        "coassignment_recall",
    ):
        assert score[metric] == 1.0
    expected_distribution = {
        "Compatible Complement": 1,
        "Conflict": 8,
        "Context-Dependent Variant": 2,
        "Near Duplicate": 9,
        "Same-Principle Variant": 6,
    }
    assert score["expected_band_distribution"] == expected_distribution
    assert score["predicted_band_distribution"] == expected_distribution
    assert score["exact_band_groups_by_label"] == expected_distribution
    assert score["exact_complete_match"] is True
    assert score["missing_gold_groups"] == []
    assert score["extra_predicted_groups"] == []
    assert run.raw_response == raw
    assert len(provider.calls) == 1
    prompt, operation, schema = provider.calls[0]
    assert operation == "task2 relation discovery"
    assert schema is not None
    assert all(
        fixture_id not in prompt
        for fixture_id in value.alias_to_fixture_id.values()
    )
    assert {
        item["id"] for item in value.left_items
    } | {
        item["id"] for item in value.right_items
    } <= set(prompt.split('"'))


@pytest.mark.parametrize("failure", ["duplicate", "missing"])
def test_provider_result_must_be_an_exact_partition(failure: str):
    corpus = load_task2_discovery_corpus(language="en")
    value = build_task2_discovery_input(corpus, group_count=2)
    response = _gold_response(value)
    relations = response["relations"]
    assert isinstance(relations, list)

    if failure == "duplicate":
        first = relations[0]
        assert isinstance(first, dict)
        left_ids = first["left_ids"]
        assert isinstance(left_ids, list)
        left_ids.append(left_ids[0])
        message = "relation members are invalid"
    else:
        relations.pop()
        message = "did not partition every left Memory once"

    provider = FakeProvider(json.dumps(response))
    with pytest.raises(Task2DiscoveryError, match=message):
        discover_task2_relations(provider, value)  # type: ignore[arg-type]


def _parity_record(
    *,
    provider: str,
    left: list[str] | tuple[str, ...],
    right: list[str] | tuple[str, ...],
    band: str = "Near Duplicate",
) -> dict[str, object]:
    return {
        "contract_valid": True,
        "pipeline": "frozen-pipeline",
        "prompt_digest": "prompt",
        "schema_digest": "schema",
        "corpus": {
            "digest": "frozen",
            "input_digest": "input",
            "alias_mapping_digest": "aliases",
            "selected_group_count": 1,
        },
        "provider": {"provider": provider},
        "predicted_relations": [
            {
                "left_fixture_ids": left,
                "right_fixture_ids": right,
                "band": band,
            }
        ],
        "expected_relations": [
            {
                "left_fixture_ids": left,
                "right_fixture_ids": right,
                "band": "Near Duplicate",
            }
        ],
    }


def test_record_parity_accepts_in_memory_tuples_and_persisted_lists():
    first = _parity_record(
        provider="codex_chatgpt",
        left=("T2-L-002", "T2-L-001"),
        right=("T2-R-001",),
    )
    second = _parity_record(
        provider="ollama",
        left=["T2-L-001", "T2-L-002"],
        right=["T2-R-001"],
    )

    parity = compare_task2_discovery_records(first, second)

    assert parity["exact_relation_agreement"] is True
    assert parity["agreed_groups"] == 1
    assert parity["first_groups"] == parity["second_groups"] == 1
    assert parity["banded_group_jaccard"] == 1.0
    assert parity["structure_group_jaccard"] == 1.0
    assert parity["coassignment_jaccard"] == 1.0
    assert parity["first_only"] == []
    assert parity["second_only"] == []


def test_record_parity_reports_a_band_disagreement():
    first = _parity_record(
        provider="codex_chatgpt",
        left=["T2-L-001"],
        right=["T2-R-001"],
    )
    second = _parity_record(
        provider="ollama",
        left=["T2-L-001"],
        right=["T2-R-001"],
        band="Conflict",
    )

    parity = compare_task2_discovery_records(first, second)

    assert parity["exact_relation_agreement"] is False
    assert parity["exact_structure_agreement"] is True
    assert parity["exact_coassignment_agreement"] is True
    assert parity["agreed_groups"] == 0
    assert parity["banded_group_jaccard"] == 0.0
    assert parity["structure_group_jaccard"] == 1.0
    assert parity["coassignment_jaccard"] == 1.0
    assert len(parity["first_only"]) == 1
    assert len(parity["second_only"]) == 1


def test_record_parity_rejects_legacy_and_v2_scorer_mismatch():
    legacy = _parity_record(
        provider="codex_chatgpt",
        left=["T2-L-001"],
        right=["T2-R-001"],
    )
    current = _parity_record(
        provider="ollama",
        left=["T2-L-001"],
        right=["T2-R-001"],
    )
    current["scorer_version"] = 2

    with pytest.raises(Task2DiscoveryError, match="different scorer versions"):
        compare_task2_discovery_records(legacy, current)


def test_campaign_locks_corpus_and_retains_invalid_provider_output(tmp_path):
    corpus = load_task2_discovery_corpus(language="en")
    value = build_task2_discovery_input(corpus, group_count=26)
    response = _gold_response(value)
    groups = response["relations"]
    assert isinstance(groups, list)
    groups.pop()
    raw = json.dumps(response, separators=(",", ":"))
    provider = CampaignProvider(raw)

    record = run_task2_discovery_campaign(
        provider,  # type: ignore[arg-type]
        ledger_dir=tmp_path,
        provider_connection_seconds=0.25,
        group_count=26,
    )

    assert record["status"] == "INVALID_OUTPUT"
    assert record["scorer_version"] == 2
    assert record["contract_valid"] is False
    assert record["lock"]["corpus_locked"] is True
    assert record["lock"]["slice_locked"] is True
    assert record["raw_response"] == raw
    assert record["score"]["exact_structure_groups"] == 25
    assert record["timing"]["provider_connection_seconds"] == 0.25
    persisted = json.loads(open(record["ledger_path"], encoding="utf-8").read())
    assert persisted["status"] == "INVALID_OUTPUT"
    assert persisted["response_digest"] == record["response_digest"]


def test_campaign_retains_provider_error_type_and_time_without_message(tmp_path):
    provider = RaisingCampaignProvider("unused")

    record = run_task2_discovery_campaign(
        provider,  # type: ignore[arg-type]
        ledger_dir=tmp_path,
        provider_connection_seconds=0.0,
        group_count=26,
        known_error_types=(ExpectedProviderFailure,),
    )

    assert record["status"] == "PROVIDER_ERROR"
    assert record["contract_valid"] is False
    assert record["provider_error_type"] == "ExpectedProviderFailure"
    assert "sensitive upstream diagnostic" not in record["validation_error"]
    assert record["raw_response"] is None
    assert record["response_digest"] is None
    assert record["timing"]["provider_completion_seconds"] >= 0.0
    persisted = json.loads(open(record["ledger_path"], encoding="utf-8").read())
    assert persisted["status"] == "PROVIDER_ERROR"
