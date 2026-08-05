"""Contracts for oracle-structure Task 2 classification diagnostics."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json

import pytest

from memcommit.eval.task2_classification import (
    TASK2_COORDINATION_VALUES,
    TASK2_OVERLAP_VALUES,
    Task2ClassificationError,
    build_task2_classification_input,
    canonical_task2_band_evidence,
    classify_task2_reviewed_groups,
    compare_task2_classification_records,
    project_task2_evidence,
    run_task2_classification_campaign,
    score_task2_classification,
)
from memcommit.eval.task2_discovery import load_task2_discovery_corpus
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
            endpoint="http://127.0.0.1:11434",
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
            prompt_tokens=100,
            completion_tokens=20,
            upstream_model=self.identity.model,
            upstream_provider=self.identity.provider,
        )
        return response


def _exact_response(value) -> dict[str, object]:
    return {
        "groups": [
            {
                "group_id": group.group_id,
                "overlap": canonical_task2_band_evidence(
                    value.group_id_to_expected[group.group_id].band
                )[0],
                "coordination": canonical_task2_band_evidence(
                    value.group_id_to_expected[group.group_id].band
                )[1],
            }
            for group in value.groups
        ]
    }


def test_classification_input_supplies_structure_but_hides_gold_identity_and_band():
    corpus = load_task2_discovery_corpus(language="en")
    value = build_task2_classification_input(corpus)
    raw = json.dumps(_exact_response(value), ensure_ascii=False)
    provider = FakeProvider(raw)

    run = classify_task2_reviewed_groups(provider, value)  # type: ignore[arg-type]

    assert len(value.groups) == len(run.predictions) == 26
    assert len(set(group.group_id for group in value.groups)) == 26
    assert all(
        len(group.group_id) == 13 and group.group_id.startswith("g")
        for group in value.groups
    )
    prompt, operation, schema = provider.calls[0]
    assert operation == "task2 reviewed-group classification"
    assert schema is not None
    assert all(band not in prompt for band in {
        relation.band for relation in value.group_id_to_expected.values()
    })
    assert all(
        relation.pair_id not in prompt
        for relation in value.group_id_to_expected.values()
    )
    assert all(
        fixture_id not in prompt
        for relation in value.group_id_to_expected.values()
        for fixture_id in (*relation.left_fixture_ids, *relation.right_fixture_ids)
    )
    assert run.raw_response == raw
    assert run.prompt_digest == hashlib.sha256(prompt.encode()).hexdigest()
    assert run.response_digest == hashlib.sha256(raw.encode()).hexdigest()


@pytest.mark.parametrize(
    ("overlap", "coordination", "band"),
    [
        ("SAME_ADVICE", "JOINT", "Near Duplicate"),
        ("SAME_PRINCIPLE", "JOINT", "Same-Principle Variant"),
        ("DIFFERENT_ADVICE", "JOINT", "Compatible Complement"),
        ("SAME_ADVICE", "CONTEXT_CHOICE", "Context-Dependent Variant"),
        ("SAME_PRINCIPLE", "CONTEXT_CHOICE", "Context-Dependent Variant"),
        ("DIFFERENT_ADVICE", "CONTEXT_CHOICE", "Context-Dependent Variant"),
        ("SAME_ADVICE", "INCOMPATIBLE", "Conflict"),
        ("SAME_PRINCIPLE", "INCOMPATIBLE", "Conflict"),
        ("DIFFERENT_ADVICE", "INCOMPATIBLE", "Conflict"),
    ],
)
def test_host_projection_is_total_and_coordination_dominates_when_not_joint(
    overlap: str, coordination: str, band: str
):
    assert project_task2_evidence(overlap, coordination) == band


def test_canonical_evidence_witnesses_project_to_every_fixture_band():
    assert {
        project_task2_evidence(*canonical_task2_band_evidence(band))
        for band in (
            "Near Duplicate",
            "Same-Principle Variant",
            "Context-Dependent Variant",
            "Conflict",
            "Compatible Complement",
        )
    } == {
        "Near Duplicate",
        "Same-Principle Variant",
        "Context-Dependent Variant",
        "Conflict",
        "Compatible Complement",
    }
    with pytest.raises(Task2ClassificationError, match="overlap"):
        project_task2_evidence("UNKNOWN", "JOINT")
    with pytest.raises(Task2ClassificationError, match="coordination"):
        project_task2_evidence("SAME_ADVICE", "UNKNOWN")


def test_fake_exact_evidence_scores_all_selected_reviewed_groups():
    corpus = load_task2_discovery_corpus(language="en")
    value = build_task2_classification_input(corpus)
    provider = FakeProvider(json.dumps(_exact_response(value)))

    run = classify_task2_reviewed_groups(provider, value)  # type: ignore[arg-type]
    score = score_task2_classification(value, run.predictions)

    assert score["expected_groups"] == score["predicted_groups"] == 26
    assert score["correct_projected_band_groups"] == 26
    assert score["projected_band_accuracy"] == 1.0
    assert score["exact_complete_match"] is True
    assert score["evidence_axis_gold_available"] is False
    assert score["missing_group_ids"] == []
    assert score["unexpected_group_ids"] == []
    assert score["incorrect_groups"] == []
    expected_distribution = Counter(
        relation.band for relation in value.group_id_to_expected.values()
    )
    assert score["expected_band_distribution"] == dict(
        sorted(expected_distribution.items())
    )
    assert score["predicted_band_distribution"] == dict(
        sorted(expected_distribution.items())
    )
    assert score["correct_groups_by_band"] == dict(
        sorted(expected_distribution.items())
    )


@pytest.mark.parametrize("failure", ["duplicate", "missing", "unknown_evidence"])
def test_provider_must_classify_each_opaque_group_exactly_once(failure: str):
    corpus = load_task2_discovery_corpus(language="en")
    value = build_task2_classification_input(corpus, group_count=2)
    response = _exact_response(value)
    groups = response["groups"]
    assert isinstance(groups, list)
    if failure == "duplicate":
        groups[1] = groups[0]
        message = "repeated a group ID"
    elif failure == "missing":
        groups.pop()
        message = "did not classify every group ID once"
    else:
        first = groups[0]
        assert isinstance(first, dict)
        first["overlap"] = "UNKNOWN"
        message = "evidence value is invalid"

    provider = FakeProvider(json.dumps(response))
    with pytest.raises(Task2ClassificationError, match=message):
        classify_task2_reviewed_groups(provider, value)  # type: ignore[arg-type]


def test_evidence_schema_uses_only_the_two_bounded_axes():
    corpus = load_task2_discovery_corpus(language="en")
    value = build_task2_classification_input(corpus, group_count=1)
    provider = FakeProvider(json.dumps(_exact_response(value)))

    classify_task2_reviewed_groups(provider, value)  # type: ignore[arg-type]

    schema = provider.calls[0][2]
    assert schema is not None
    groups_schema = schema["properties"]["groups"]  # type: ignore[index]
    item_schema = groups_schema["items"]  # type: ignore[index]
    properties = item_schema["properties"]  # type: ignore[index]
    assert set(properties) == {"group_id", "overlap", "coordination"}
    assert properties["overlap"]["enum"] == list(TASK2_OVERLAP_VALUES)
    assert properties["coordination"]["enum"] == list(
        TASK2_COORDINATION_VALUES
    )


def test_campaign_retains_raw_digests_stage_timing_and_score(tmp_path):
    corpus = load_task2_discovery_corpus(language="en")
    value = build_task2_classification_input(corpus, group_count=2)
    raw = json.dumps(_exact_response(value), separators=(",", ":"))
    provider = CampaignProvider(raw)

    record = run_task2_classification_campaign(
        provider,  # type: ignore[arg-type]
        ledger_dir=tmp_path,
        provider_connection_seconds=0.25,
        group_count=2,
    )

    assert record["contract_valid"] is True
    assert record["status"] == "COMPLETED"
    assert record["raw_response"] == raw
    assert record["response_digest"] == hashlib.sha256(raw.encode()).hexdigest()
    assert record["prompt_digest"]
    assert record["schema_digest"]
    corpus_record = record["corpus"]
    assert corpus_record["input_digest"] == value.input_digest
    assert corpus_record["group_mapping_digest"] == value.group_mapping_digest
    timing = record["timing"]
    assert set(timing) == {
        "provider_connection_seconds",
        "corpus_preparation_seconds",
        "input_preparation_seconds",
        "prompt_preparation_seconds",
        "provider_completion_seconds",
        "response_validation_seconds",
        "scoring_seconds",
        "campaign_seconds",
        "total_seconds",
    }
    assert timing["provider_connection_seconds"] == 0.25
    assert all(value >= 0 for value in timing.values())
    assert record["score"]["projected_band_accuracy"] == 1.0
    ledger_path = record["ledger_path"]
    persisted = json.loads(open(ledger_path, encoding="utf-8").read())
    assert persisted["raw_response"] == raw
    assert persisted["provider_run"]["completion_tokens"] == 20


def test_classification_parity_separates_agreement_from_reviewed_gold(tmp_path):
    corpus = load_task2_discovery_corpus(language="en")
    value = build_task2_classification_input(corpus, group_count=2)
    raw = json.dumps(_exact_response(value), separators=(",", ":"))
    provider = CampaignProvider(raw)
    first = run_task2_classification_campaign(
        provider,  # type: ignore[arg-type]
        ledger_dir=tmp_path,
        provider_connection_seconds=0.0,
        group_count=2,
    )
    second = deepcopy(first)
    prediction = second["predictions"][0]
    prediction["overlap"] = "DIFFERENT_ADVICE"
    prediction["coordination"] = "INCOMPATIBLE"
    prediction["projected_band"] = "Conflict"

    parity = compare_task2_classification_records(first, second)

    assert parity["expected_groups"] == parity["common_groups"] == 2
    assert parity["projected_band_agreement"] == 1
    assert parity["evidence_agreement"] == 1
    assert parity["both_gold"] == 1
    assert parity["first_only_gold"] == 1
    assert parity["second_only_gold"] == 0
    assert parity["parity_gate_passed"] is False
