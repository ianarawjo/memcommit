"""Terminal checkpoint evidence exposed by post-application Review."""

from __future__ import annotations

import click
import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.applied_checkpoint_review import (
    applied_checkpoint_review_controller,
    list_applied_checkpoint_reviews,
    select_applied_checkpoint_review,
)
from memcommit.context import AutoCheckpoint
from memcommit.cli import app
from memcommit.commands.review_report import run_review_report_shell
from memcommit.interfaces.console.theme import (
    SemanticColorRole,
    semantic_color_rgb,
)
from memcommit.resolution_workbench import ResolutionWorkbenchAction
from memcommit.store import MemoryStore


runner = CliRunner()


def test_checkpoint_review_discovers_and_renders_exact_applied_effects(
    isolated_store,
):
    store = MemoryStore()
    context = ops.init("review/forget")
    checkpoint = store.create_context(
        context,
        AutoCheckpoint(
            command="forget",
            args={
                "query": "remove old preference",
                "effects": [
                    {
                        "kind": "REMOVE",
                        "memory_uid": "memory-1",
                        "before": "Old preference.",
                        "after": None,
                        "reason": "Matched the instruction.",
                    }
                ],
            },
            description="Removed one matching Memory",
        ),
    )
    assert checkpoint is not None

    records = list_applied_checkpoint_reviews(store, "forget")

    assert len(records) == 1
    assert records[0].checkpoint_uid == checkpoint.uid
    report = applied_checkpoint_review_controller(records[0]).report()
    assert "STATUS · APPLIED" in report.report_text
    assert "BEFORE · Old preference." in report.report_text
    assert "WHY · Matched the instruction." in report.report_text
    assert "read-only" in report.summary


def test_checkpoint_review_requires_an_unambiguous_receipt_prefix(isolated_store):
    records = ()

    with pytest.raises(ValueError, match="unavailable or ambiguous"):
        select_applied_checkpoint_review(records, "deadbeef")


def test_review_command_opens_exact_applied_checkpoint_without_a_provider(
    isolated_store,
):
    store = MemoryStore()
    context = ops.init("review/resolve")
    checkpoint = store.create_context(
        context,
        AutoCheckpoint(
            command="resolve",
            args={
                "effects": [
                    {
                        "kind": "EDIT",
                        "memory_uid": "memory-1",
                        "before": "The old reading.",
                        "after": "The grounded reading.",
                        "reason": "The complete frame independently verified YES.",
                    }
                ]
            },
            description="Applied one grounded Resolve plan",
        ),
    )
    assert checkpoint is not None

    result = runner.invoke(
        app,
        ["review", "resolve", "--receipt", checkpoint.uid[:8], "--snapshot"],
    )

    assert result.exit_code == 0, result.output
    assert "MEM REVIEW · RESOLVE" in result.output
    assert "STATUS · APPLIED" in result.output
    assert "BEFORE · The old reading." in result.output
    assert "AFTER · The grounded reading." in result.output


def test_dedun_review_combines_survivor_identity_and_content_without_keep_row(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context = ops.init("review/dedun")
    checkpoint = store.create_context(
        context,
        AutoCheckpoint(
            command="dedun",
            args={
                "components": [
                    {
                        "survivor_uid": "survivor-11111111",
                        "members": [
                            {
                                "uid": "survivor-11111111",
                                "content": "Canonical retained Memory.",
                                "selected": True,
                            },
                            {
                                "uid": "absorbed-22222222",
                                "content": "Redundant absorbed Memory.",
                                "selected": False,
                            },
                        ],
                        "evidence": [],
                    }
                ]
            },
            description="Resolved one redundancy group",
        ),
    )
    assert checkpoint is not None

    record = select_applied_checkpoint_review(
        list_applied_checkpoint_reviews(store, "dedun"),
        checkpoint.uid[:8],
    )
    controller = applied_checkpoint_review_controller(record)
    captured: dict[str, object] = {}

    def run_shell(_view, **kwargs):
        captured.update(kwargs)
        return ResolutionWorkbenchAction(kind="CLOSE")

    monkeypatch.setattr(
        "memcommit.commands.review_report.run_resolution_workbench_shell",
        run_shell,
    )
    run_review_report_shell(
        controller,
        interactive_actions=False,
        require_tty=False,
    )
    tui_fragments = captured["split_report_fragments"]
    assert isinstance(tui_fragments, tuple)
    assert ("class:impact.add", "SURVIVOR") in tui_fragments
    assert ("class:impact.remove", "ABSORB") in tui_fragments

    result = runner.invoke(
        app,
        ["review", "dedun", "--receipt", checkpoint.uid[:8], "--snapshot"],
        color=True,
    )

    assert result.exit_code == 0, result.output
    plain = click.unstyle(result.output)
    assert "SURVIVOR · [survivor] Canonical retained Memory." in plain
    assert "KEEP ·" not in plain
    assert "ABSORB · [absorbed] Redundant absorbed Memory." in plain
    assert click.style(
        "SURVIVOR",
        fg=semantic_color_rgb(SemanticColorRole.ADD),
        bold=True,
    ) in result.output
    assert click.style(
        "ABSORB",
        fg=semantic_color_rgb(SemanticColorRole.REMOVE),
        bold=True,
    ) in result.output
