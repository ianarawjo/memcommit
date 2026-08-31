"""Bounded default Compare summary without an exhaustive ledger."""

from __future__ import annotations

import json
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.adapters.console.commands.compare.command as compare_command
import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.model import ComparisonInput
from memcommit.core.context import MemoryRef
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.repository import comparison_analysis_path
from memcommit.application.operations.compare.compare_summary import ComparisonSummaryError
from memcommit.application.operations.compare.provider_contract import summarize_comparison
from memcommit.providers.policy import ResolvedProviderPolicy
from memcommit.providers.profile_routes import (
    ProfileProviderRoutesError,
)
from memcommit.persistence.store import MemoryStore


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
                "text": (
                    "Both peers require a concise proposal, while the reference "
                    "also asks for descriptive headings and the peer prefers "
                    "active voice."
                ),
                "source_ids": [*reference_ids, *compared_ids],
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
    assert summary.paragraph.text.startswith("Both peers")
    assert summary.source_count == 2


def test_summary_treats_live_embed_content_as_an_ordinary_claim():
    owner = ops.init("summary/embed-owner")
    source = ops.add(owner, "Embedded summary claim.")
    reference = ops.init("summary/embed-reference")
    reference.add(
        MemoryRef(
            uid=str(uuid.uuid4()),
            target_context_uid=owner.uid,
            target_context_name=owner.name,
            target_memory_uid=source.uid,
            target=source,
        )
    )
    compared = ops.init("summary/embed-peer")
    ops.add(compared, "Peer summary claim.")
    provider = ConciseCompareProvider()

    summary = summarize_comparison(
        ComparisonInput.from_contexts(reference, compared),
        provider,
    )
    payload = json.loads(
        provider.prompts[0].split("COMPARISON SUMMARY PAYLOAD:\n", 1)[1]
    )

    assert summary.source_count == 2
    assert payload["frames"][0]["memories"][0]["content"] == source.content
    assert "owner_context" not in json.dumps(payload)
    assert "source_form" not in json.dumps(payload)


def test_default_cli_reports_an_unavailable_profile_provider_without_traceback(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    reference, compared = _pair(store)

    def unavailable_provider(_operation):
        raise ProfileProviderRoutesError("Study provider policy is unavailable.")

    monkeypatch.setattr(
        compare_command,
        "connect_operation_provider",
        unavailable_provider,
    )

    result = runner.invoke(app, ["compare", reference.name, compared.name])

    assert result.exit_code == 1
    assert result.output == (
        "Compare error: Study provider policy is unavailable.\n"
    )
    assert "Traceback" not in result.output


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
                    "text": "This claims to compare both sides.",
                    "source_ids": [reference_id],
                }
            )

    with pytest.raises(ComparisonSummaryError, match="cite both peer sides"):
        summarize_comparison(
            ComparisonInput.from_contexts(reference, compared),
            OneSidedProvider(),
        )


def test_summary_rejects_provider_authored_line_breaks():
    reference = ops.init("summary/reference")
    ops.add(reference, "Reference claim.")
    compared = ops.init("summary/peer")
    ops.add(compared, "Peer claim.")

    class SectionedProvider(ConciseCompareProvider):
        def complete(self, prompt, *, operation, output_schema=None):
            payload = json.loads(
                prompt.split("COMPARISON SUMMARY PAYLOAD:\n", 1)[1]
            )
            reference_id = payload["frames"][0]["memories"][0]["id"]
            compared_id = payload["frames"][1]["memories"][0]["id"]
            return json.dumps(
                {
                    "text": "BOTH\nThe claims overlap.",
                    "source_ids": [reference_id, compared_id],
                }
            )

    with pytest.raises(ComparisonSummaryError, match="exactly one prose paragraph"):
        summarize_comparison(
            ComparisonInput.from_contexts(reference, compared),
            SectionedProvider(),
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
    assert f"Compare · {reference.name} ↔ {compared.name}" in result.output
    assert "\nCOMPARISON\n" in result.output
    assert "Both peers require a concise proposal" in result.output
    assert "MEM COMPARE · SUMMARY" not in result.output
    assert "READ-ONLY · TRANSIENT · NO RELATION LEDGER" not in result.output
    assert "SCOPE ·" not in result.output
    assert "\nOVERVIEW\n" not in result.output
    assert "\nBOTH\n" not in result.output
    assert "\nDIFFERENCES\n" not in result.output
    assert "Deep relation analysis is available" not in result.output
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
    assert "\nCOMPARISON\n" not in result.output
    assert not comparison_analysis_path(reference.uid, compared.uid).exists()
