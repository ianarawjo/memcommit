from __future__ import annotations

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.commands.context_picker import ContextMemorySelection
from memcommit.context import Memory
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


@pytest.mark.parametrize("command", ("delete", "remove"))
def test_both_spellings_delete_an_existing_context(isolated_store, command):
    store = MemoryStore()
    store.create_context(ops.init("victim"))
    store.create_context(ops.init("keeper"))
    store.set_current("keeper")

    result = runner.invoke(app, [command, "victim", "--force"])

    assert result.exit_code == 0, result.output
    assert "Deleted context 'victim'" in result.output
    assert not store.context_exists("victim")


@pytest.mark.parametrize("command", ("delete", "remove"))
def test_both_spellings_remove_a_direct_memory(isolated_store, command):
    store = MemoryStore()
    context = ops.init("owner")
    memory = ops.add(context, "remove me")
    store.create_context(context)
    store.set_current(context.name)

    result = runner.invoke(app, [command, memory.uid[:8]])

    assert result.exit_code == 0, result.output
    assert f"Removed [{memory.uid[:8]}]" in result.output
    assert memory.uid not in store.load_direct(context.name).memories


@pytest.mark.parametrize("command", ("delete", "remove"))
def test_both_spellings_resolve_relative_context_locators(
    isolated_store,
    command,
):
    store = MemoryStore()
    store.create_context(ops.init("project/victim"))
    store.create_context(ops.init("project/current"))
    store.set_current("project/current")

    result = runner.invoke(app, [command, "../victim", "--force"])

    assert result.exit_code == 0, result.output
    assert "Deleted context 'project/victim'" in result.output
    assert not store.context_exists("project/victim")


@pytest.mark.parametrize("command", ("delete", "remove"))
def test_explicit_context_scopes_selector_to_a_direct_item(
    isolated_store,
    command,
):
    store = MemoryStore()
    owner = ops.init("owner")
    memory = ops.add(owner, "remove me")
    store.create_context(owner)
    store.create_context(ops.init(memory.uid[:8]))

    result = runner.invoke(
        app,
        [command, memory.uid[:8], "--context", owner.name],
    )

    assert result.exit_code == 0, result.output
    assert store.context_exists(memory.uid[:8])
    assert memory.uid not in store.load_direct(owner.name).memories


@pytest.mark.parametrize("command", ("delete", "remove"))
def test_combined_selector_rejects_context_and_item_collision(
    isolated_store,
    command,
):
    store = MemoryStore()
    owner = ops.init("owner")
    memory = Memory(
        uid="deadbeef-1111-1111-1111-111111111111",
        content="keep me",
    )
    owner.add(memory)
    store.create_context(owner)
    store.create_context(ops.init("deadbeef"))
    store.set_current(owner.name)

    result = runner.invoke(app, [command, "deadbeef", "--force"])

    assert result.exit_code == 1
    assert "matches both Context 'deadbeef' and direct item [deadbeef]" in result.stderr
    assert store.context_exists("deadbeef")
    assert memory.uid in store.load_direct(owner.name).memories


@pytest.mark.parametrize("command", ("delete", "remove"))
def test_both_spellings_use_shared_picker_for_context_selection(
    isolated_store,
    monkeypatch,
    command,
):
    store = MemoryStore()
    store.create_context(ops.init("victim"))
    store.create_context(ops.init("keeper"))
    store.set_current("keeper")
    observed: dict[str, object] = {}

    def choose(names, **kwargs):
        observed["names"] = names
        observed.update(kwargs)
        return "victim"

    monkeypatch.setattr("memcommit.commands.delete.choose_context", choose)

    result = runner.invoke(app, [command, "--force"])

    assert result.exit_code == 0, result.output
    assert observed["selectable_memories"] is True
    assert observed["initially_show_memories"] is True
    assert not store.context_exists("victim")


@pytest.mark.parametrize("command", ("delete", "remove"))
def test_both_spellings_apply_exact_picker_item_receipt(
    isolated_store,
    monkeypatch,
    command,
):
    store = MemoryStore()
    owner = ops.init("owner")
    memory = ops.add(owner, "remove me")
    store.create_context(owner)
    store.set_current(owner.name)

    monkeypatch.setattr(
        "memcommit.commands.delete.choose_context",
        lambda *_args, **_kwargs: ContextMemorySelection(
            context_name=owner.name,
            selector=memory.uid,
        ),
    )

    result = runner.invoke(app, [command])

    assert result.exit_code == 0, result.output
    assert memory.uid not in store.load_direct(owner.name).memories
