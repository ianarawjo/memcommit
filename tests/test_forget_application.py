"""Forget application-boundary, no-op, freshness, and recovery contracts."""

from __future__ import annotations

import json

from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.commands import forget as forget_command
from memcommit.context import AutoCheckpoint
from memcommit.semantic.changes import RemoveChange
from memcommit.store import MemoryStore


runner = CliRunner()


def _forget_source(name: str = "forget/application"):
    store = MemoryStore()
    context = ops.init(name)
    memory = ops.add(context, "The service desk used to be beside the west entrance.")
    store.create_context(context)
    store.set_current(name)
    return store, context, memory


def _remove(memory):
    return RemoveChange(
        uid=memory.uid,
        content=memory.content,
        reason="The reviewed instruction covers this Memory.",
    )


def _stub_tty_forget(monkeypatch, result, *, interactive: bool = True):
    monkeypatch.setattr(
        forget_command,
        "_interactive_terminal",
        lambda: interactive,
    )
    monkeypatch.setattr(
        forget_command,
        "connect_codex_chatgpt_provider",
        lambda: object(),
    )
    monkeypatch.setattr(
        forget_command,
        "_run_interactive_forget",
        result if callable(result) else lambda *_args, **_kwargs: result,
    )


def test_local_forget_applies_once_and_undo_redo_restore_the_batch(
    isolated_store,
    monkeypatch,
):
    store, context, memory = _forget_source()
    checkpoint_count = len(store.list_checkpoints(context.name))
    _stub_tty_forget(monkeypatch, [_remove(memory)])

    applied = runner.invoke(app, ["forget", "Forget the old service desk."])

    assert applied.exit_code == 0, applied.output + applied.stderr
    assert "FORGET APPLIED · SOURCE forget/application" in applied.output
    assert "EFFECTS · REMOVE 1 · EDIT 0" in applied.output
    assert "RECOVERY · mem undo" in applied.output
    assert memory.uid not in store.load_direct(context.name).memories
    assert len(store.list_checkpoints(context.name)) == checkpoint_count + 1

    undone = runner.invoke(app, ["undo"])
    assert undone.exit_code == 0, undone.output + undone.stderr
    assert "Undid command: mem forget" in undone.output
    assert memory.uid in store.load_direct(context.name).memories

    redone = runner.invoke(app, ["redo"])
    assert redone.exit_code == 0, redone.output + redone.stderr
    assert "Redid command: mem forget" in redone.output
    assert memory.uid not in store.load_direct(context.name).memories


def test_explicit_non_tty_forget_advances_decisions_without_a_proposal_prompt(
    isolated_store,
    monkeypatch,
):
    store, context, memory = _forget_source("forget/direct-execution")

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            assert operation == "forget"
            messages = json.loads(prompt.split("FORGET CHAT MESSAGES:\n", 1)[1])
            payload = json.loads(
                messages[1]["content"].split("FORGET PAYLOAD:\n", 1)[1]
            )
            [source] = payload["source"]["memories"]
            return json.dumps(
                {
                    "overview": "The instruction covers the old location.",
                    "candidates": [
                        {
                            "source_memory_id": source["item_id"],
                            "decision": "DELETE",
                            "proposed_content": "",
                            "rationale": "Matched the complete instruction.",
                            "criterion_item_ids": ["k1"],
                        }
                    ],
                }
            )

    monkeypatch.setattr(forget_command, "_interactive_terminal", lambda: False)
    monkeypatch.setattr(
        forget_command,
        "connect_codex_chatgpt_provider",
        Provider,
    )

    result = runner.invoke(app, ["forget", "Forget the old service desk."])

    assert result.exit_code == 0, result.output
    assert "FORGET APPLIED · SOURCE forget/direct-execution" in result.output
    assert "Proposed changes" not in result.output
    assert "Apply this" not in result.output
    assert "REVIEW · mem review forget --receipt" in result.output
    assert memory.uid not in store.load_direct(context.name).memories


def test_forget_all_keep_is_a_visible_noop_without_a_checkpoint(
    isolated_store,
    monkeypatch,
):
    store, context, memory = _forget_source("forget/noop")
    before = store.list_checkpoints(context.name)
    _stub_tty_forget(monkeypatch, [])

    result = runner.invoke(app, ["forget", "Forget nothing here."])

    assert result.exit_code == 0, result.output + result.stderr
    assert (
        "FORGET COMPLETE · SOURCE forget/noop\n"
        "OUTCOME · NO CHANGE · Context unchanged · no checkpoint"
    ) in result.output
    assert store.list_checkpoints(context.name) == before
    assert memory.uid in store.load_direct(context.name).memories


def test_forget_cancel_is_distinct_from_an_accepted_noop(
    isolated_store,
    monkeypatch,
):
    store, context, memory = _forget_source("forget/cancel")
    before = store.list_checkpoints(context.name)
    _stub_tty_forget(monkeypatch, None)

    result = runner.invoke(app, ["forget", "Forget the old service desk."])

    assert result.exit_code == 0, result.output + result.stderr
    assert (
        "Forget cancelled · SOURCE forget/cancel · Context unchanged"
        in result.output
    )
    assert "Forget complete" not in result.output
    assert store.list_checkpoints(context.name) == before
    assert memory.uid in store.load_direct(context.name).memories


def test_forget_rejects_a_stale_review_without_publishing_a_partial_change(
    isolated_store,
    monkeypatch,
):
    store, context, memory = _forget_source("forget/stale")

    def concurrent_change(_ctx, _info, _provider, **_kwargs):
        current = MemoryStore().load_direct(context.name)
        concurrent = ops.add(current, "A concurrent note must survive.")
        MemoryStore().save(
            current,
            AutoCheckpoint(
                command="add",
                args={},
                description="Concurrent test change.",
            ),
        )
        concurrent_change.uid = concurrent.uid
        return [_remove(memory)]

    _stub_tty_forget(monkeypatch, concurrent_change, interactive=False)

    result = runner.invoke(app, ["forget", "Forget the old service desk."])

    assert result.exit_code == 1
    assert "changed before it could be saved" in result.output
    assert "Done:" not in result.output
    current = store.load_direct(context.name)
    assert memory.uid in current.memories
    assert concurrent_change.uid in current.memories
    assert [entry["command"] for entry in store.list_checkpoints(context.name)].count(
        "forget"
    ) == 0
