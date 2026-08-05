"""Contracts for the reusable Context understanding-summary unit."""
from __future__ import annotations

import json

from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.comparison import ComparisonInput
from memcommit.comparison_provider import analyze_comparison
from memcommit.summarize import SUMMARIZE_OPERATION
from memcommit.store import MemoryStore
from memcommit.understanding import UnderstandingSummary


runner = CliRunner()


class SummaryProvider:
    def __init__(self, *, invalid_source: bool = False):
        self.invalid_source = invalid_source
        self.calls: list[tuple[str, dict[str, object]]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == SUMMARIZE_OPERATION
        assert output_schema is not None
        payload = json.loads(prompt.split("SUMMARIZE CONTEXT PAYLOAD:\n", 1)[1])
        self.calls.append((prompt, output_schema))
        source_ids = [item["source_id"] for item in payload["memories"]]
        return json.dumps(
            {
                "text": (
                    "The Context describes a closure while preserving an "
                    "explicit staff-access exception."
                ),
                "source_ids": (
                    ["unknown-source"] if self.invalid_source else source_ids
                ),
            }
        )


def test_mem_summarize_recurses_and_renders_only_shared_understanding(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    child = ops.init("summary/child")
    ops.add(child, "Staff retain card access during the closure.")
    root = ops.init("summary")
    ops.add(root, "The building closes on Friday.")
    ops.embed(child, root)
    store.save(child)
    store.save(root)
    provider = SummaryProvider()
    monkeypatch.setattr(
        "memcommit.commands.summarize.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    result = runner.invoke(app, ["summarize", "summary"])

    assert result.exit_code == 0
    assert "SUMMARY · summary" in result.output
    assert "STATUS · READ-ONLY · RECURSIVE" in result.output
    assert "WHAT MEM UNDERSTOOD" in result.output
    assert "WHAT HAPPENED" not in result.output
    assert "WHAT BOTH CONTAIN" not in result.output
    payload = json.loads(
        provider.calls[0][0].split("SUMMARIZE CONTEXT PAYLOAD:\n", 1)[1]
    )
    assert [item["context"] for item in payload["memories"]] == [
        "summary",
        "summary/child",
    ]


def test_mem_summarize_direct_excludes_child_memories(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    child = ops.init("summary/child")
    ops.add(child, "Child-only material.")
    root = ops.init("summary")
    ops.add(root, "Root material.")
    ops.embed(child, root)
    store.save(child)
    store.save(root)
    provider = SummaryProvider()
    monkeypatch.setattr(
        "memcommit.commands.summarize.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    result = runner.invoke(app, ["summarize", "summary", "--direct"])

    assert result.exit_code == 0
    assert "STATUS · READ-ONLY · DIRECT" in result.output
    payload = json.loads(
        provider.calls[0][0].split("SUMMARIZE CONTEXT PAYLOAD:\n", 1)[1]
    )
    assert [item["content"] for item in payload["memories"]] == [
        "Root material."
    ]


def test_mem_summarize_empty_context_is_provider_free(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    store.save(ops.init("empty-summary"))

    def forbidden():
        raise AssertionError("empty summarize must not connect a provider")

    monkeypatch.setattr(
        "memcommit.commands.summarize.connect_codex_chatgpt_provider",
        forbidden,
    )

    result = runner.invoke(app, ["summarize", "empty-summary"])

    assert result.exit_code == 0
    assert "contains no ordinary Memories to summarize" in result.output


def test_mem_summarize_rejects_unknown_evidence_alias(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("invalid-summary")
    ops.add(ctx, "Evidence.")
    store.save(ctx)
    provider = SummaryProvider(invalid_source=True)
    monkeypatch.setattr(
        "memcommit.commands.summarize.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    result = runner.invoke(app, ["summarize", "invalid-summary"])

    assert result.exit_code == 1
    assert "Summarize error" in result.output
    assert "Invalid understanding summary sources" in result.output


def test_mem_summarize_rejects_source_change_before_publishing(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("changing-summary")
    ops.add(ctx, "Initial evidence.")
    store.save(ctx)

    class MutatingProvider(SummaryProvider):
        def complete(self, prompt, *, operation, output_schema=None):
            response = super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )
            changed = store.load("changing-summary")
            ops.add(changed, "Concurrent evidence.")
            store.save(changed)
            return response

    monkeypatch.setattr(
        "memcommit.commands.summarize.connect_codex_chatgpt_provider",
        lambda: MutatingProvider(),
    )

    result = runner.invoke(app, ["summarize", "changing-summary"])

    assert result.exit_code == 1
    assert "changed while summarization was running" in result.output
    assert "WHAT MEM UNDERSTOOD" not in result.output


class PairProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        payload = json.loads(prompt.split("COMPARISON PAYLOAD:\n", 1)[1])
        left = payload["frames"][0]["memories"][0]["memory_id"]
        right = payload["frames"][1]["memories"][0]["memory_id"]
        return json.dumps(
            {
                "overview": "Both Contexts describe the same access rule.",
                "reports": {
                    "both": "Both require staff card access.",
                    "differences": "",
                    "reference_only": "",
                    "compared_only": "",
                },
                "relations": [
                    {
                        "relation_key": "shared",
                        "reference_memory_ids": [left],
                        "compared_memory_ids": [right],
                        "kind": "EQUIVALENT",
                        "status": "RESOLVED",
                        "summary": "The access rules match.",
                        "reason": "The credential and scope are the same.",
                    }
                ],
                "issues": [],
            }
        )


def test_compare_exposes_its_overview_as_the_shared_understanding_unit(
    isolated_store,
):
    left = ops.init("left")
    ops.add(left, "Staff use a card.")
    right = ops.init("right")
    ops.add(right, "Staff use a card.")

    analysis = analyze_comparison(
        ComparisonInput.from_contexts(left, right),
        PairProvider(),
    )

    assert isinstance(analysis.understanding, UnderstandingSummary)
    assert analysis.overview == analysis.understanding.text
    assert len(analysis.understanding.source_uids) == 2
