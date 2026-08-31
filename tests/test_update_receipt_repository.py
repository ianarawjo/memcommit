"""Durable Update receipt repository across active singleton replacement."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.commands.operation_lifecycle.impact.catalog import impact_session_entries
from memcommit.adapters.console.commands.operation_lifecycle.review.sessions import review_session_entries
from memcommit.persistence.store import MemoryStore
from memcommit.application.operations.semantic_updates.foundation.update.model import plan_update
from memcommit.persistence.operations.update.receipt_repository import (
    UpdateReceiptRepository,
)


runner = CliRunner(mix_stderr=False)


class NoChangeProvider:
    def complete(self, _prompt, *, operation, output_schema=None):
        assert operation == "update planning"
        return json.dumps({"edits": [], "additions": [], "removals": []})


def _staged_update(store: MemoryStore):
    return plan_update(
        store.load("source"),
        store.load("target"),
        lambda: NoChangeProvider(),
        status="staged",
    )


def _store_with_update_inputs() -> MemoryStore:
    store = MemoryStore()
    source = ops.init("source")
    ops.add(source, "Verified source evidence.")
    target = ops.init("target")
    ops.add(target, "Existing target statement.")
    store.save(source)
    store.save(target)
    return store


def test_completed_update_remains_reviewable_after_next_stage(isolated_store):
    store = _store_with_update_inputs()
    first = _staged_update(store)
    store.save_staged_update(first)
    applied = store.apply_staged_update(first)

    second = _staged_update(store)
    store.save_staged_update(second)

    assert store.load_staged_update() == second
    assert UpdateReceiptRepository(store).load(applied.uid) == applied
    reviewed = runner.invoke(
        app,
        ["review", "update", "--session", applied.uid[:8], "--snapshot"],
    )
    assert reviewed.exit_code == 0, reviewed.output
    assert "MEM REVIEW · UPDATE" in reviewed.output
    assert "0 EDITS · 0 ADDITIONS · 0 REMOVALS" in reviewed.output
    impacted = runner.invoke(
        app,
        ["impact", "update", "--session", applied.uid[:8]],
    )
    assert impacted.exit_code == 0, impacted.output
    assert "IMPACT · UPDATE" in impacted.output


def test_retained_update_is_listed_by_review_and_impact_launchers(isolated_store):
    store = _store_with_update_inputs()
    staged = _staged_update(store)
    store.save_staged_update(staged)
    applied = store.apply_staged_update(staged)
    store.save_staged_update(_staged_update(store))

    assert ("update", applied.uid) in {
        (entry.kind, entry.key) for entry in review_session_entries(store)
    }
    assert ("update", applied.uid) in {
        (entry.kind, entry.key) for entry in impact_session_entries(store)
    }


def test_terminal_pair_rolls_back_active_slot_when_receipt_save_fails(
    isolated_store,
    monkeypatch,
):
    store = _store_with_update_inputs()
    staged = _staged_update(store)
    store.save_staged_update(staged)
    monkeypatch.setattr(
        UpdateReceiptRepository,
        "save_terminal",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            OSError("simulated receipt failure")
        ),
    )

    with pytest.raises(OSError, match="simulated receipt failure"):
        store.apply_staged_update(staged)

    assert store.load_staged_update() == staged
    assert not (isolated_store / "update-receipts").exists()
