"""Contracts for evidence-bound Context-to-Context Distill."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
import memcommit.commands.distill as distill_command
from memcommit.cli import app
from memcommit.commands.help_inventory import COMMAND_FORMS
from memcommit.context import Context, Memory
from memcommit.distill import (
    DISTILL_OPERATION,
    DISTILL_PAYLOAD_MARKER,
    DistillError,
    analyze_distill,
)
from memcommit.distill_application import DistillApplyRequest, DistillRequest
from memcommit.distill_runtime import execute_distill, execute_distill_apply
from memcommit.store import MemoryStore
from memcommit.summarize import collect_summary_frame


runner = CliRunner()


class DistillProvider:
    def __init__(self, response=None):
        self.response = response
        self.calls: list[tuple[str, dict[str, object]]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == DISTILL_OPERATION
        assert output_schema is not None
        self.calls.append((prompt, output_schema))
        payload = json.loads(prompt.split(DISTILL_PAYLOAD_MARKER, 1)[1])
        aliases = [item["memory_id"] for item in payload["source"]["memories"]]
        response = self.response or {
            "overview": "The evidence supports one bounded interaction Rule.",
            "rules": [
                {
                    "content": (
                        "When conversation is the purpose, prefer a quiet setting "
                        "and confirm the final choice with the user."
                    ),
                    "rationale": (
                        "The Goal requires a recommendation and the examples "
                        "distinguish quiet from noisy settings."
                    ),
                    "goal_support": True,
                    "support_memory_ids": aliases[:1],
                    "boundary_memory_ids": aliases[1:2],
                }
            ],
            "outside_memory_ids": aliases[2:],
        }
        return json.dumps(response)


def _frame() -> tuple[Context, object]:
    context = Context(uid="00000000-0000-4000-8000-000000000001", name="cases")
    context.add(
        Memory(
            uid="00000000-0000-4000-8000-000000000011",
            content="A quiet family meal made conversation easy.",
        )
    )
    context.add(
        Memory(
            uid="00000000-0000-4000-8000-000000000012",
            content="At a loud restaurant, the user left after 30 minutes.",
        )
    )
    return context, collect_summary_frame(context)


def test_distill_accepts_goal_and_context_evidence_as_one_rule_frame():
    _context, frame = _frame()
    provider = DistillProvider()

    analysis = analyze_distill(
        frame,
        goal="Recommend a setting for a family conversation.",
        provider=provider,
    )

    assert len(analysis.rules) == 1
    rule = analysis.rules[0]
    assert rule.goal_support is True
    assert rule.support_memory_uids == (
        "00000000-0000-4000-8000-000000000011",
    )
    assert rule.boundary_memory_uids == (
        "00000000-0000-4000-8000-000000000012",
    )
    assert analysis.outside_memory_uids == ()
    payload = json.loads(provider.calls[0][0].split(DISTILL_PAYLOAD_MARKER, 1)[1])
    assert payload["goal"] == "Recommend a setting for a family conversation."


def test_distill_rejects_silent_source_omission():
    _context, frame = _frame()
    provider = DistillProvider(
        {
            "overview": "Incomplete accounting.",
            "rules": [
                {
                    "content": "Prefer quiet settings.",
                    "rationale": "One case supports it.",
                    "goal_support": False,
                    "support_memory_ids": ["m000001"],
                    "boundary_memory_ids": [],
                }
            ],
            "outside_memory_ids": [],
        }
    )

    with pytest.raises(DistillError, match="account for every Source Memory"):
        analyze_distill(frame, goal=None, provider=provider)


def test_distill_schema_leaves_uniqueness_to_the_strict_local_decoder():
    _context, frame = _frame()
    provider = DistillProvider()

    analyze_distill(
        frame,
        goal="Recommend a setting for a family conversation.",
        provider=provider,
    )

    schema = provider.calls[0][1]
    encoded = json.dumps(schema, sort_keys=True)
    assert "uniqueItems" not in encoded


def test_distill_local_decoder_rejects_duplicate_source_aliases():
    _context, frame = _frame()
    provider = DistillProvider(
        {
            "overview": "Duplicate evidence is invalid.",
            "rules": [
                {
                    "content": "Prefer quiet settings.",
                    "rationale": "One case supports it.",
                    "goal_support": False,
                    "support_memory_ids": ["m000001", "m000001"],
                    "boundary_memory_ids": ["m000002"],
                }
            ],
            "outside_memory_ids": [],
        }
    )

    with pytest.raises(DistillError, match="duplicate source aliases"):
        analyze_distill(frame, goal=None, provider=provider)


def test_distill_goal_only_can_support_a_rule_in_an_empty_context():
    empty = Context(uid="00000000-0000-4000-8000-000000000021", name="empty")
    frame = collect_summary_frame(empty)
    provider = DistillProvider(
        {
            "overview": "The Goal itself supplies one durable constraint.",
            "rules": [
                {
                    "content": "Confirm the final choice with the user.",
                    "rationale": "The supplied Goal explicitly requires confirmation.",
                    "goal_support": True,
                    "support_memory_ids": [],
                    "boundary_memory_ids": [],
                }
            ],
            "outside_memory_ids": [],
        }
    )

    analysis = analyze_distill(
        frame,
        goal="Recommend an option, then confirm the final choice with the user.",
        provider=provider,
    )

    assert analysis.rules[0].goal_support is True
    assert analysis.rules[0].support_memory_uids == ()


def test_execute_and_apply_distill_create_new_result_and_preserve_source(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("distill/cases")
    first = ops.add(source, "A quiet family meal made conversation easy.")
    second = ops.add(source, "At a loud restaurant, the user left early.")
    store.save(source)
    store.set_current(source.name)
    provider = DistillProvider()

    result = execute_distill(
        DistillRequest(
            context_locator=source.name,
            goal="Recommend a setting for a family conversation.",
        ),
        store=store,
        provider_factory=lambda: provider,
    )

    assert store.load_direct(source.name).ordered_uids() == [first.uid, second.uid]
    assert not store.context_exists("distill/rules")

    receipt = execute_distill_apply(
        DistillApplyRequest(result=result, output_name="distill/rules"),
        store=store,
    )

    output = store.load_direct("distill/rules")
    assert output.uid == receipt.output_context_uid
    assert output.ordered_uids() == list(receipt.result_memory_uids)
    assert "prefer a quiet setting" in next(iter(output.iter_items())).content
    assert store.load_direct(source.name).ordered_uids() == [first.uid, second.uid]
    checkpoints = store.list_checkpoints("distill/rules")
    assert checkpoints[0]["command"] == "distill"
    metadata = checkpoints[0]["args"]["distill"]
    assert metadata["source_context"] == source.name
    assert metadata["rules"][0]["support_memory_uids"] == [first.uid]
    assert metadata["rules"][0]["boundary_memory_uids"] == [second.uid]


def test_distill_apply_fails_closed_when_source_changed(isolated_store):
    store = MemoryStore()
    source = ops.init("distill/stale")
    ops.add(source, "One source case.")
    store.save(source)
    provider = DistillProvider(
        {
            "overview": "One Rule is supported.",
            "rules": [
                {
                    "content": "Retain the supported source condition.",
                    "rationale": "The single Source Memory supports it.",
                    "goal_support": False,
                    "support_memory_ids": ["m000001"],
                    "boundary_memory_ids": [],
                }
            ],
            "outside_memory_ids": [],
        }
    )
    result = execute_distill(
        DistillRequest(context_locator=source.name),
        store=store,
        provider_factory=lambda: provider,
    )
    changed = store.load_direct(source.name)
    ops.add(changed, "A concurrent Source change.")
    store.save(changed)

    with pytest.raises(DistillError, match="Source changed before Apply"):
        execute_distill_apply(
            DistillApplyRequest(result=result, output_name="distill/stale-rules"),
            store=store,
        )
    assert not store.context_exists("distill/stale-rules")


def test_mem_distill_applies_the_exact_rendered_proposal(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("distill/cli-cases")
    ops.add(source, "A quiet family meal made conversation easy.")
    ops.add(source, "At a loud restaurant, the user left early.")
    store.save(source)
    provider = DistillProvider()
    monkeypatch.setattr(
        distill_command,
        "connect_semantic_provider",
        lambda: provider,
    )

    result = runner.invoke(
        app,
        [
            "distill",
            source.name,
            "--goal",
            "Recommend a setting for a family conversation.",
            "--save-as",
            "distill/cli-rules",
            "--apply",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "STATUS · REVIEW ONLY · SOURCE UNCHANGED" in result.output
    assert "Created Distill Result 'distill/cli-rules' with 1 Rules" in result.output
    assert store.context_exists("distill/cli-rules")
    assert len(store.load_direct(source.name).order) == 2


def test_mem_distill_save_as_without_apply_remains_read_only(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("distill/preview")
    ops.add(source, "One supported source case.")
    store.save(source)
    provider = DistillProvider(
        {
            "overview": "One Rule is supported.",
            "rules": [
                {
                    "content": "Retain the supported source condition.",
                    "rationale": "The Source Memory supports it.",
                    "goal_support": False,
                    "support_memory_ids": ["m000001"],
                    "boundary_memory_ids": [],
                }
            ],
            "outside_memory_ids": [],
        }
    )
    monkeypatch.setattr(
        distill_command,
        "connect_semantic_provider",
        lambda: provider,
    )

    result = runner.invoke(
        app,
        ["distill", source.name, "--save-as", "distill/preview-rules"],
    )

    assert result.exit_code == 0, result.output
    assert "NOT CREATED" in result.output
    assert not store.context_exists("distill/preview-rules")


def test_mem_distill_help_inventory_exposes_goal_review_and_apply_forms():
    assert COMMAND_FORMS["distill"] == (
        "mem distill (review Rules distilled from the current Context)",
        "mem distill [context] (review Rules from one explicit Context)",
        'mem distill [context] --goal "[goal]" (guide Rule relevance with a Goal)',
        "mem distill [context] -r (include descendants and embedded Contexts)",
        "mem distill [context] --save-as [result_context] "
        "(review without creating the Result)",
        "mem distill [context] --save-as [result_context] --apply "
        "(create the exact reviewed Rule Context)",
    )
