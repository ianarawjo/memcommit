"""Direct-item commands must preserve unresolved embedded Context pointers."""

from __future__ import annotations

from typer.testing import CliRunner

import memcommit.commands.add as add_command
import memcommit.commands.forget as forget_command
import memcommit.ops as ops
from memcommit.cli import app
from memcommit.context import Memory
from memcommit.semantic.changes import RemoveChange
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _dangling_parent(
    *,
    contents: tuple[str, ...] = ("original",),
) -> tuple[MemoryStore, str, tuple[Memory, ...], str]:
    """Return a current parent whose serialized child pointer is unresolved."""
    store = MemoryStore()
    child = ops.init("child")
    store.save(child)

    parent = ops.init("parent")
    memories = tuple(ops.add(parent, content) for content in contents)
    ops.embed(child, parent)
    store.save(parent)
    store.set_current(parent.name)
    store.delete(child.name)

    assert store.load_direct(parent.name).to_dict()["memories"][child.uid][
        "type"
    ] == "context_ref"
    return store, parent.name, memories, child.uid


def _assert_context_ref(
    store: MemoryStore,
    context_name: str,
    reference_uid: str,
) -> None:
    record = store.load_direct(context_name).to_dict()
    assert record["memories"][reference_uid]["type"] == "context_ref"


def test_add_preserves_unresolved_context_ref(isolated_store):
    store, name, _, reference_uid = _dangling_parent()

    result = runner.invoke(app, ["add", "added"])

    assert result.exit_code == 0, result.output
    _assert_context_ref(store, name, reference_uid)
    assert [
        item.content
        for item in store.load_direct(name).iter_items()
        if isinstance(item, Memory)
    ] == ["original", "added"]


def test_add_paste_reload_preserves_unresolved_context_ref(
    isolated_store,
    monkeypatch,
):
    store, name, _, reference_uid = _dangling_parent()
    monkeypatch.setattr(add_command, "capture_paste", lambda: "pasted")

    result = runner.invoke(app, ["add", "--paste"], input="y\n")

    assert result.exit_code == 0, result.output
    _assert_context_ref(store, name, reference_uid)


def test_edit_preserves_unresolved_context_ref(isolated_store):
    store, name, memories, reference_uid = _dangling_parent()

    result = runner.invoke(
        app,
        ["edit", memories[0].uid[:8], "edited"],
    )

    assert result.exit_code == 0, result.output
    _assert_context_ref(store, name, reference_uid)
    edited = store.load_direct(name).memories[memories[0].uid]
    assert isinstance(edited, Memory)
    assert edited.content == "edited"


def test_remove_can_delete_unresolved_context_ref(isolated_store):
    store, name, memories, reference_uid = _dangling_parent()

    result = runner.invoke(app, ["remove", reference_uid[:8]])

    assert result.exit_code == 0, result.output
    context = store.load_direct(name)
    assert reference_uid not in context.memories
    assert memories[0].uid in context.memories


def test_chunk_preserves_unresolved_context_ref(isolated_store):
    store, name, memories, reference_uid = _dangling_parent(
        contents=("First paragraph.\n\nSecond paragraph.",),
    )

    result = runner.invoke(
        app,
        ["chunk", memories[0].uid[:8]],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    _assert_context_ref(store, name, reference_uid)
    assert len(
        [
            item
            for item in store.load_direct(name).iter_items()
            if isinstance(item, Memory)
        ]
    ) == 2


def test_forget_preserves_unresolved_context_ref(
    isolated_store,
    monkeypatch,
):
    store, name, memories, reference_uid = _dangling_parent()

    def apply_forget(context, _info, _llm):
        memory = memories[0]
        context.remove(memory.uid)
        return [
            RemoveChange(
                uid=memory.uid,
                content=memory.content,
                reason="test",
            )
        ]

    monkeypatch.setattr(
        forget_command,
        "connect_codex_chatgpt_provider",
        lambda: object(),
    )
    monkeypatch.setattr(
        forget_command,
        "_run_interactive_forget",
        apply_forget,
    )

    result = runner.invoke(app, ["forget", "remove original"])

    assert result.exit_code == 0, result.output
    _assert_context_ref(store, name, reference_uid)
    assert memories[0].uid not in store.load_direct(name).memories


def test_clear_counts_and_removes_unresolved_context_ref(isolated_store):
    store, name, _, _ = _dangling_parent(contents=())

    result = runner.invoke(app, ["clear", "--force"])

    assert result.exit_code == 0, result.output
    assert "Cleared 1 item(s)" in result.output
    assert store.load_direct(name).memories == {}
    checkpoint = store.list_checkpoints(name)[0]
    assert checkpoint["command"] == "clear"
    assert checkpoint["snapshot"]["memories"] == {}


def test_checkpoint_records_unresolved_context_ref(isolated_store):
    store, name, _, reference_uid = _dangling_parent(contents=())

    result = runner.invoke(app, ["checkpoint", "pointer snapshot"])

    assert result.exit_code == 0, result.output
    checkpoint = store.list_checkpoints(name)[0]
    assert checkpoint["snapshot"]["memories"][reference_uid]["type"] == (
        "context_ref"
    )
    assert checkpoint["auto"] is False


def test_direct_mutations_still_checkpoint_once(isolated_store):
    store, name, _, reference_uid = _dangling_parent()

    result = runner.invoke(app, ["add", "checkpointed"])

    assert result.exit_code == 0, result.output
    checkpoints = store.list_checkpoints(name)
    assert len(checkpoints) == 1
    assert checkpoints[0]["command"] == "add"
    assert checkpoints[0]["snapshot"]["memories"][reference_uid]["type"] == (
        "context_ref"
    )
