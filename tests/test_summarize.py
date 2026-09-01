"""Contracts for the reusable Context understanding-summary unit."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.clipboard import ClipboardError
import memcommit.adapters.console.commands.summarize.command as summarize_command
from memcommit.adapters.console.commands.help.command import COMMAND_FORMS
from memcommit.adapters.console.entrypoint import app
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.model import (
    ComparisonInput,
)
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.provider_contract import (
    analyze_comparison,
)
from memcommit.core.context import Memory
from memcommit.application.operations.summarize.model import (
    SUMMARIZE_OPERATION,
    SummarizeError,
    collect_summary_scope,
)
from memcommit.persistence.store import MemoryStore
from memcommit.application.capabilities.semantic.understanding import (
    UnderstandingSummary,
    parse_source_linked_understanding,
)


runner = CliRunner()


def test_understanding_deduplicates_two_aliases_for_one_durable_memory():
    summary = parse_source_linked_understanding(
        {
            "text": "The same durable evidence is visible through two Context aliases.",
            "source_ids": ["m000001", "m000002"],
        },
        source_uid_by_id={
            "m000001": "shared-memory-uid",
            "m000002": "shared-memory-uid",
        },
    )

    assert summary.source_uids == ("shared-memory-uid",)


def test_summary_scope_rejects_conflicting_payloads_for_one_memory_uid():
    first = ops.init("summary/first")
    second = ops.init("summary/second")
    first.add(Memory(uid="shared-memory-uid", content="First payload."))
    second.add(Memory(uid="shared-memory-uid", content="Conflicting payload."))

    with pytest.raises(SummarizeError, match="conflicting content"):
        collect_summary_scope(
            (first, second),
            root_context_uid=first.uid,
            root_context_name="summary",
            include_descendants=True,
            follow_embeds=True,
        )


def test_mem_summarize_inventory_matches_direct_default_and_copy_contract():
    assert COMMAND_FORMS["summarize"] == (
        "mem summarize (direct summary of the current Context)",
        "mem summarize [context] (direct summary of an explicit Context)",
        "mem summarize -r (recursive summary of the current Context)",
        "mem summarize [context] -r (lexical descendants and embedded Contexts)",
        "mem summarize [context] --copy "
        "(copy verified direct understanding as plain text)",
    )


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
        "memcommit.adapters.console.commands.summarize.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    result = runner.invoke(app, ["summarize", "summary", "-r"])

    assert result.exit_code == 0
    assert "SUMMARY · summary" in result.output
    assert "STATUS · RECURSIVE" in result.output
    assert "WHAT MEM UNDERSTOOD" not in result.output
    assert "The Context describes a closure" in result.output
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
        "memcommit.adapters.console.commands.summarize.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    result = runner.invoke(app, ["summarize", "summary", "-d"])

    assert result.exit_code == 0
    assert "STATUS · DIRECT" in result.output
    payload = json.loads(
        provider.calls[0][0].split("SUMMARIZE CONTEXT PAYLOAD:\n", 1)[1]
    )
    assert [item["content"] for item in payload["memories"]] == ["Root material."]


def test_mem_summarize_recursive_includes_unembedded_lexical_descendants(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    child = ops.init("summary/child")
    ops.add(child, "Lexical child material.")
    root = ops.init("summary")
    store.save(child)
    store.save(root)
    provider = SummaryProvider()
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.summarize.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    result = runner.invoke(app, ["summarize", "summary", "--recursive"])

    assert result.exit_code == 0
    payload = json.loads(
        provider.calls[0][0].split("SUMMARIZE CONTEXT PAYLOAD:\n", 1)[1]
    )
    assert [item["context"] for item in payload["memories"]] == ["summary/child"]


def test_mem_summarize_rejects_direct_and_recursive_together(isolated_store):
    store = MemoryStore()
    store.save(ops.init("summary"))

    result = runner.invoke(app, ["summarize", "summary", "-d", "-r"])

    assert result.exit_code == 1
    assert "Choose either --direct/-d or --recursive/-r" in result.output


def test_mem_summarize_rejects_retired_presentation_flags_before_execution(
    isolated_store,
    monkeypatch,
):
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.summarize.command.MemoryStore",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("retired flag parsing must not open the Store")
        ),
    )

    result = runner.invoke(app, ["summarize", "summary", "--tui"])

    assert result.exit_code == 2
    assert "No such option: --tui" in result.output


def test_mem_summarize_plain_preserves_noninteractive_output(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    store.save(ops.init("plain-summary"))
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.summarize.command.connect_codex_chatgpt_provider",
        lambda: (_ for _ in ()).throw(
            AssertionError("empty summary must remain provider-free")
        ),
    )

    result = runner.invoke(
        app,
        ["summarize", "plain-summary"],
    )

    assert result.exit_code == 0
    assert "SUMMARY · plain-summary" in result.output
    assert "STATUS · DIRECT" in result.output
    assert "contains no ordinary Memories to summarize" in result.output


def test_mem_summarize_copy_writes_plain_understanding_without_typed_stage(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context = ops.init("summary")
    ops.add(context, "Copy this source-grounded commitment.")
    store.save(context)
    provider = SummaryProvider()
    copied: list[str] = []
    monkeypatch.setattr(
        summarize_command,
        "connect_codex_chatgpt_provider",
        lambda: provider,
    )
    monkeypatch.setattr(summarize_command, "write_system_clipboard", copied.append)

    result = runner.invoke(app, ["summarize", "summary", "--copy"])

    assert result.exit_code == 0, result.output
    assert copied == [
        "The Context describes a closure while preserving an explicit "
        "staff-access exception."
    ]
    assert "Copied Summary as plain text to the system clipboard." in result.output
    assert not (isolated_store / "clipboard.json").exists()


def test_mem_summarize_copy_failure_keeps_result_visible_and_fails_cleanly(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context = ops.init("summary")
    ops.add(context, "Visible result survives a clipboard failure.")
    store.save(context)
    provider = SummaryProvider()
    monkeypatch.setattr(
        summarize_command,
        "connect_codex_chatgpt_provider",
        lambda: provider,
    )

    def fail_copy(_text: str) -> None:
        raise ClipboardError("clipboard unavailable")

    monkeypatch.setattr(summarize_command, "write_system_clipboard", fail_copy)

    result = runner.invoke(app, ["summarize", "summary", "--copy"])

    assert result.exit_code == 1
    assert "WHAT MEM UNDERSTOOD" not in result.stdout
    assert "The Context describes a closure" in result.stdout
    assert "Copy error: clipboard unavailable" in result.output


def test_mem_summarize_empty_context_is_provider_free(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    store.save(ops.init("empty-summary"))

    def forbidden():
        raise AssertionError("empty summarize must not connect a provider")

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.summarize.command.connect_codex_chatgpt_provider",
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
        "memcommit.adapters.console.commands.summarize.command.connect_codex_chatgpt_provider",
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
        "memcommit.adapters.console.commands.summarize.command.connect_codex_chatgpt_provider",
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
