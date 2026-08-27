"""Opt-in lexical parent creation for `mem init`."""

from __future__ import annotations

from typer.testing import CliRunner

from memcommit.adapters.console.entrypoint import app
from memcommit.context import Context
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def test_init_parents_creates_each_missing_context_without_embedding(
    isolated_store,
) -> None:
    result = runner.invoke(
        app,
        ["init", "--parents", "test/update/from"],
    )

    assert result.exit_code == 0, result.output
    assert "Ensured context hierarchy 'test/update/from'." in result.output
    assert "Created: test, test/update, test/update/from" in result.output
    assert "Current: test/update/from" in result.output
    store = MemoryStore()
    assert store.list_context_names() == [
        "test",
        "test/update",
        "test/update/from",
    ]
    assert store.current_context_name() == "test/update/from"
    for name in store.list_context_names():
        context = store.load_direct(name)
        assert context.memories == {}
        checkpoints = store.list_checkpoints(name)
        assert len(checkpoints) == 1
        assert checkpoints[0]["args"] == {
            "name": name,
            "parents": True,
            "requested_name": "test/update/from",
        }
    assert not any(
        isinstance(item, Context)
        for item in store.load("test").iter_items()
    )


def test_init_parents_backfills_existing_leaf_and_preserves_sibling(
    isolated_store,
) -> None:
    assert runner.invoke(app, ["init", "test/update/from"]).exit_code == 0
    assert runner.invoke(
        app,
        ["add", "Existing leaf fact."],
    ).exit_code == 0
    leaf_context_file = (
        isolated_store
        / "contexts"
        / "test"
        / "update"
        / "from"
        / "context.json"
    )
    leaf_checkpoints_dir = leaf_context_file.parent / "checkpoints"
    leaf_context_bytes = leaf_context_file.read_bytes()
    leaf_checkpoint_bytes = {
        path.name: path.read_bytes()
        for path in leaf_checkpoints_dir.iterdir()
    }
    assert runner.invoke(app, ["init", "test/update/to"]).exit_code == 0
    store = MemoryStore()
    leaf_before = store.load_direct("test/update/from")
    leaf_history = store.list_checkpoints("test/update/from")
    sibling_before = store.load_direct("test/update/to")

    result = runner.invoke(
        app,
        ["init", "-p", "test/update/from"],
    )

    assert result.exit_code == 0, result.output
    assert "Created: test, test/update" in result.output
    assert "Reused: test/update/from" in result.output
    assert store.list_context_names() == [
        "test",
        "test/update",
        "test/update/from",
        "test/update/to",
    ]
    assert store.current_context_name() == "test/update/from"
    assert store.load_direct("test/update/from").uid == leaf_before.uid
    assert store.list_checkpoints("test/update/from") == leaf_history
    assert store.load_direct("test/update/to").uid == sibling_before.uid
    assert leaf_context_file.read_bytes() == leaf_context_bytes
    assert {
        path.name: path.read_bytes()
        for path in leaf_checkpoints_dir.iterdir()
    } == leaf_checkpoint_bytes


def test_init_parents_reuses_existing_prefix_without_modifying_it(
    isolated_store,
) -> None:
    assert runner.invoke(app, ["init", "test"]).exit_code == 0
    assert runner.invoke(app, ["add", "Existing root fact."]).exit_code == 0
    store = MemoryStore()
    root_before = store.load_direct("test")
    root_history = store.list_checkpoints("test")

    result = runner.invoke(
        app,
        ["init", "--parents", "test/update/from"],
    )

    assert result.exit_code == 0, result.output
    assert "Created: test/update, test/update/from" in result.output
    assert "Reused: test" in result.output
    root_after = store.load_direct("test")
    assert root_after.uid == root_before.uid
    assert [
        item.content
        for item in root_after.iter_items()
    ] == ["Existing root fact."]
    assert store.list_checkpoints("test") == root_history


def test_init_parents_is_idempotent_when_the_full_hierarchy_exists(
    isolated_store,
) -> None:
    first = runner.invoke(
        app,
        ["init", "--parents", "test/update/from"],
    )
    assert first.exit_code == 0
    store = MemoryStore()
    identities = {
        name: store.load_direct(name).uid
        for name in store.list_context_names()
    }
    histories = {
        name: store.list_checkpoints(name)
        for name in store.list_context_names()
    }

    second = runner.invoke(
        app,
        ["init", "--parents", "test/update/from"],
    )

    assert second.exit_code == 0, second.output
    assert "Created: (none)" in second.output
    assert "Reused: test, test/update, test/update/from" in second.output
    assert {
        name: store.load_direct(name).uid
        for name in store.list_context_names()
    } == identities
    assert {
        name: store.list_checkpoints(name)
        for name in store.list_context_names()
    } == histories


def test_init_parents_prevalidates_every_prefix_before_writing(
    isolated_store,
) -> None:
    result = runner.invoke(
        app,
        ["init", "--parents", "test/checkpoints/from"],
    )

    assert result.exit_code == 1
    assert "reserved" in result.stderr
    assert MemoryStore().list_context_names() == []


def test_init_parents_late_storage_preflight_failure_creates_no_prefix(
    isolated_store,
) -> None:
    MemoryStore()
    blocked = (
        isolated_store
        / "contexts"
        / "test"
        / "update"
        / "from"
    )
    blocked.mkdir(parents=True)
    sentinel = blocked / "keep.txt"
    sentinel.write_text("keep")

    result = runner.invoke(
        app,
        ["init", "--parents", "test/update/from"],
    )

    assert result.exit_code == 1
    assert "already exists and is not empty" in result.stderr
    assert MemoryStore().list_context_names() == []
    assert sentinel.read_text() == "keep"


def test_init_parents_rolls_back_only_new_contexts_on_late_failure(
    isolated_store,
    monkeypatch,
) -> None:
    original = MemoryStore._save_locked

    def fail_leaf(self, context, *args, **kwargs):
        if context.name == "test/update/from":
            raise OSError("forced leaf failure")
        return original(self, context, *args, **kwargs)

    monkeypatch.setattr(MemoryStore, "_save_locked", fail_leaf)

    result = runner.invoke(
        app,
        ["init", "--parents", "test/update/from"],
    )

    assert result.exit_code == 1
    assert "forced leaf failure" in result.stderr
    store = MemoryStore()
    assert store.list_context_names() == []
    assert store.current_context_name() is None


def test_init_parents_rolls_back_fresh_hierarchy_when_selection_fails(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    original = MemoryStore._write_state

    def fail_selection(self, state):
        if state.get("current") == "test/update/from":
            raise OSError("forced state failure")
        return original(self, state)

    monkeypatch.setattr(MemoryStore, "_write_state", fail_selection)

    result = runner.invoke(
        app,
        ["init", "--parents", "test/update/from"],
    )

    assert result.exit_code == 1
    assert "forced state failure" in result.stderr
    assert store.list_context_names() == []
    assert store.current_context_name() is None


def test_init_parents_state_failure_preserves_reused_leaf_and_current(
    isolated_store,
    monkeypatch,
) -> None:
    assert runner.invoke(app, ["init", "test/update/from"]).exit_code == 0
    assert runner.invoke(app, ["init", "other"]).exit_code == 0
    store = MemoryStore()
    leaf_uid = store.load_direct("test/update/from").uid
    leaf_history = store.list_checkpoints("test/update/from")
    original = MemoryStore._write_state

    def fail_selection(self, state):
        if state.get("current") == "test/update/from":
            raise OSError("forced state failure")
        return original(self, state)

    monkeypatch.setattr(MemoryStore, "_write_state", fail_selection)

    result = runner.invoke(
        app,
        ["init", "--parents", "test/update/from"],
    )

    assert result.exit_code == 1
    assert "forced state failure" in result.stderr
    assert store.list_context_names() == ["other", "test/update/from"]
    assert store.load_direct("test/update/from").uid == leaf_uid
    assert store.list_checkpoints("test/update/from") == leaf_history
    assert store.current_context_name() == "other"
