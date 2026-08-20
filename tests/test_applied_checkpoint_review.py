"""Terminal checkpoint evidence exposed by post-application Review."""

from __future__ import annotations

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
    store = MemoryStore()
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
