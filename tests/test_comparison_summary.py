"""Bounded default Compare summary without an exhaustive ledger."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import memcommit.commands.compare as compare_command
import memcommit.ops as ops
from memcommit.cli import app
from memcommit.comparison import ComparisonInput
from memcommit.comparison_store import comparison_analysis_path
from memcommit.comparison_summary import ComparisonSummaryError
from memcommit.comparison_summary_provider import summarize_comparison
from memcommit.infrastructure.providers.policy import ResolvedProviderPolicy
from memcommit.store import MemoryStore


runner = CliRunner()


class ConciseCompareProvider:
    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.schemas: list[dict[str, object]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        self.prompts.append(prompt)
        assert output_schema is not None
        self.schemas.append(output_schema)
        payload = json.loads(prompt.split("COMPARISON SUMMARY PAYLOAD:\n", 1)[1])
        reference_ids = [row["id"] for row in payload["frames"][0]["memories"]]
        compared_ids = [row["id"] for row in payload["frames"][1]["memories"]]
        return json.dumps(
            {
                "overview": {
                    "text": "Both peers constrain the same proposal in different ways.",
                    "source_ids": [reference_ids[0], compared_ids[0]],
                },
                "both": {
                    "text": "Both require a concise proposal.",
                    "source_ids": [reference_ids[0], compared_ids[0]],
                },
                "differences": {"text": "", "source_ids": []},
                "reference_only": {
                    "text": "The reference also asks for headings.",
                    "source_ids": [reference_ids[-1]],
                },
                "compared_only": {
                    "text": "The peer also asks for active voice.",
                    "source_ids": [compared_ids[-1]],
                },
            }
        )


def _pair(store: MemoryStore):
    reference = ops.init("summary/reference")
    ops.add(reference, "Keep the proposal concise.")
    ops.add(reference, "Use descriptive headings.")
    compared = ops.init("summary/peer")
    ops.add(compared, "The proposal must be concise.")
    ops.add(compared, "Prefer active voice.")
    store.create_context(reference)
    store.create_context(compared)
    store.set_current(reference.name)
    return reference, compared


def test_summary_contract_has_no_relation_or_issue_output_shape():
    reference = ops.init("summary/reference")
    ops.add(reference, "Keep the proposal concise.")
    compared = ops.init("summary/peer")
    ops.add(compared, "The proposal must be concise.")
    provider = ConciseCompareProvider()

    summary = summarize_comparison(
        ComparisonInput.from_contexts(reference, compared),
        provider,
    )

    schema_text = json.dumps(provider.schemas[0], sort_keys=True)
    assert "relations" not in schema_text
    assert "issues" not in schema_text
    assert "assignments" not in schema_text
    assert summary.overview.text.startswith("Both peers")
    assert summary.source_count == 2


def test_summary_rejects_one_sided_evidence_for_a_cross_frame_claim():
    reference = ops.init("summary/reference")
    ops.add(reference, "Reference claim.")
    compared = ops.init("summary/peer")
    ops.add(compared, "Peer claim.")

    class OneSidedProvider(ConciseCompareProvider):
        def complete(self, prompt, *, operation, output_schema=None):
            payload = json.loads(
                prompt.split("COMPARISON SUMMARY PAYLOAD:\n", 1)[1]
            )
            reference_id = payload["frames"][0]["memories"][0]["id"]
            return json.dumps(
                {
                    "overview": {
                        "text": "This claims to compare both sides.",
                        "source_ids": [reference_id],
                    },
                    "both": {"text": "", "source_ids": []},
                    "differences": {"text": "", "source_ids": []},
                    "reference_only": {"text": "", "source_ids": []},
                    "compared_only": {"text": "", "source_ids": []},
                }
            )

    with pytest.raises(ComparisonSummaryError, match="cite both peer sides"):
        summarize_comparison(
            ComparisonInput.from_contexts(reference, compared),
            OneSidedProvider(),
        )


def test_default_cli_is_transient_and_ledger_is_explicit(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    reference, compared = _pair(store)
    provider = ConciseCompareProvider()
    policy = ResolvedProviderPolicy(
        operation="compare_summary",
        mode="PRODUCTION",
        provider_id="codex_chatgpt",
        model="test-model",
        reasoning_effort="none",
        timeout_seconds=30.0,
        source="GLOBAL_DEFAULT",
    )
    monkeypatch.setattr(
        compare_command,
        "connect_operation_provider",
        lambda _operation: (provider, policy),
    )

    result = runner.invoke(
        app,
        ["compare", "--to", compared.name, "--snapshot"],
    )

    assert result.exit_code == 0, result.output
    assert "MEM COMPARE · SUMMARY" in result.output
    assert "READ-ONLY · TRANSIENT · NO RELATION LEDGER" in result.output
    assert "Both peers constrain" in result.output
    assert "Deep relation analysis is available with mem compare --ledger" in (
        result.output.replace("\n", " ")
    )
    assert len(provider.prompts) == 1
    assert not comparison_analysis_path(reference.uid, compared.uid).exists()


def test_default_cli_suppresses_a_summary_when_a_source_changes_in_flight(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    reference, compared = _pair(store)

    class MutatingProvider(ConciseCompareProvider):
        def complete(self, prompt, *, operation, output_schema=None):
            changed = store.load_direct(compared.name)
            ops.add(changed, "This arrived during lightweight comparison.")
            store.save(changed)
            return super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )

    provider = MutatingProvider()
    policy = ResolvedProviderPolicy(
        operation="compare_summary",
        mode="PRODUCTION",
        provider_id="codex_chatgpt",
        model="test-model",
        reasoning_effort="none",
        timeout_seconds=30.0,
        source="GLOBAL_DEFAULT",
    )
    monkeypatch.setattr(
        compare_command,
        "connect_operation_provider",
        lambda _operation: (provider, policy),
    )

    result = runner.invoke(app, ["compare", "--to", compared.name])

    assert result.exit_code == 1
    assert "changed while Compare was summarizing" in result.output
    assert "MEM COMPARE · SUMMARY" not in result.output
    assert not comparison_analysis_path(reference.uid, compared.uid).exists()
