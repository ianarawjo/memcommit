"""State-oriented contracts for ``mem undo``."""
from __future__ import annotations

from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.store import MemoryStore


runner = CliRunner()


def invoke(*args: str):
    return runner.invoke(app, list(args))


def test_undo_restores_the_previous_distinct_context_state(isolated_store):
    invoke("init", "notes")
    invoke("add", "keep")
    invoke("add", "undo me")

    result = invoke("undo")

    assert result.exit_code == 0
    assert "Undid the last Context state change" in result.output
    contents = [
        memory.content
        for memory in MemoryStore().load_current().memories.values()
    ]
    assert contents == ["keep"]


def test_undo_skips_manual_checkpoints_with_the_same_snapshot(isolated_store):
    invoke("init", "notes")
    invoke("add", "keep")
    invoke("checkpoint", "duplicate one")
    invoke("checkpoint", "duplicate two")

    result = invoke("undo")

    assert result.exit_code == 0
    assert not MemoryStore().load_current().memories


def test_undo_after_revert_restores_the_pre_revert_state(isolated_store):
    invoke("init", "notes")
    store = MemoryStore()
    init_uid = store.list_checkpoints("notes")[0]["uid"]
    invoke("add", "restore me")
    invoke("revert", init_uid[:8])
    assert not store.load_current().memories

    result = invoke("undo")

    assert result.exit_code == 0
    restored = store.load_current()
    assert [memory.content for memory in restored.memories.values()] == [
        "restore me"
    ]


def test_undo_restores_newest_checkpoint_from_uncheckpointed_state(
    isolated_store,
):
    invoke("init", "notes")
    invoke("add", "saved")
    store = MemoryStore()
    context = store.load_current()
    context.add("not checkpointed")
    store.save(context)

    result = invoke("undo")

    assert result.exit_code == 0
    restored = store.load_current()
    assert [memory.content for memory in restored.memories.values()] == [
        "saved"
    ]


def test_undo_normalizes_inherited_checkpoint_identity(isolated_store):
    invoke("init", "source")
    invoke("add", "inherited")
    invoke("branch", "branch")
    invoke("add", "branch only")

    result = invoke("undo")

    assert result.exit_code == 0
    restored = MemoryStore().load_current()
    assert restored.name == "branch"
    assert [memory.content for memory in restored.memories.values()] == [
        "inherited"
    ]


def test_undo_race_at_locked_revert_preserves_concurrent_state(
    isolated_store,
    monkeypatch,
):
    invoke("init", "notes")
    invoke("add", "keep")
    invoke("add", "undo me")
    store = MemoryStore()
    original_revert = MemoryStore.revert
    state_after_race = {}

    def race_before_locked_revert(
        self,
        context_name,
        uid_prefix,
        keep_history=False,
        **expectations,
    ):
        concurrent = self.load_direct(context_name)
        ops.add(concurrent, "concurrent")
        self.save(concurrent)
        state_after_race["context"] = self.load_direct(
            context_name
        ).to_dict()
        state_after_race["history"] = self.list_checkpoints(context_name)
        return original_revert(
            self,
            context_name,
            uid_prefix,
            keep_history=keep_history,
            **expectations,
        )

    monkeypatch.setattr(MemoryStore, "revert", race_before_locked_revert)

    result = invoke("undo")

    assert result.exit_code == 1
    assert "changed before the reviewed revert" in result.output
    assert store.load_direct("notes").to_dict() == state_after_race["context"]
    assert store.list_checkpoints("notes") == state_after_race["history"]


def test_undo_fails_without_an_earlier_distinct_state(isolated_store):
    store = MemoryStore()
    context = ops.init("bare")
    store.save(context)
    store.set_current("bare")

    result = invoke("undo")

    assert result.exit_code == 1
    assert "no earlier distinct state" in result.output


def test_undo_fails_without_a_current_context(isolated_store):
    result = invoke("undo")

    assert result.exit_code == 1
    assert "No current context" in result.output
