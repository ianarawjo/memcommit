from __future__ import annotations

import click
import json
import pytest
import uuid
from typer.testing import CliRunner

import memcommit.application.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.shared.context_picker import ContextMemorySelection
from memcommit.core.context import Context, Memory
from memcommit.persistence.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _write_legacy_context(store: MemoryStore, name: str) -> None:
    """Install a pre-reservation Context name for compatibility coverage."""

    context = Context(uid=str(uuid.uuid4()), name=name)
    path = store._context_file(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(context.to_dict()), encoding="utf-8")


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

    result = runner.invoke(app, [command, memory.uid[:8]], color=True)

    assert result.exit_code == 0, result.output
    assert result.output == (
        click.style(f"Removed [{memory.uid[:8]}] ", fg="green")
        + click.style(memory.content, fg="red")
        + "\n"
    )
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


def test_context_delete_keeps_human_confirmation_and_cancel_is_read_only(
    isolated_store,
):
    store = MemoryStore()
    store.create_context(ops.init("victim"))

    result = runner.invoke(app, ["delete", "victim"], input="n\n")

    assert result.exit_code == 1
    assert "Continue? [y/N]" in result.output
    assert store.context_exists("victim")


@pytest.mark.parametrize("command", ("delete", "remove"))
def test_explicit_context_scopes_selector_to_a_direct_item(
    isolated_store,
    command,
):
    store = MemoryStore()
    owner = ops.init("owner")
    memory = ops.add(owner, "remove me")
    store.create_context(owner)

    result = runner.invoke(
        app,
        [command, memory.uid[:8], "--context", owner.name],
    )

    assert result.exit_code == 0, result.output
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
    # New UID-shaped root names are reserved, but a legacy Store may still
    # contain one and must keep the combined-selector fail-closed behavior.
    _write_legacy_context(store, "deadbeef")
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

    selections = iter(("victim", None))

    def choose(names, **kwargs):
        observed["names"] = names
        observed.update(kwargs)
        return next(selections)

    monkeypatch.setattr("memcommit.adapters.console.commands.delete.command.choose_context", choose)

    result = runner.invoke(app, [command, "--force"])

    assert result.exit_code == 0, result.output
    assert observed["selectable_memories"] is True
    assert observed["initially_show_memories"] is True
    assert observed["exit_label"] == "close"
    assert callable(observed["nested_accept_handler"])
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

    receipts = []

    def choose(*_args, **kwargs):
        receipts.append(
            kwargs["nested_accept_handler"](
                owner.name,
                memory.uid,
            )
        )
        return None

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.delete.command.choose_context",
        choose,
    )

    result = runner.invoke(app, [command])

    assert result.exit_code == 0, result.output
    assert result.output == ""
    assert receipts[0].label == "REMOVED"
    assert receipts[0].detail_style == receipts[0].label_style
    assert memory.uid not in store.load_direct(owner.name).memories


@pytest.mark.parametrize("command", ("delete", "remove"))
def test_picker_session_removes_multiple_items_until_closed(
    isolated_store,
    monkeypatch,
    command,
):
    store = MemoryStore()
    owner = ops.init("owner")
    first = ops.add(owner, "remove first")
    second = ops.add(owner, "remove second")
    store.create_context(owner)
    store.set_current(owner.name)
    initial_targets: list[str | ContextMemorySelection | None] = []
    receipts = []

    def choose(*_args, **kwargs):
        initial_targets.append(kwargs["initial_target"])
        handler = kwargs["nested_accept_handler"]
        receipts.extend(
            (
                handler(owner.name, first.uid),
                handler(owner.name, second.uid),
            )
        )
        return None

    monkeypatch.setattr("memcommit.adapters.console.commands.delete.command.choose_context", choose)

    result = runner.invoke(app, [command])

    assert result.exit_code == 0, result.output
    assert store.load_direct(owner.name).memories == {}
    assert result.output == ""
    assert [receipt.label for receipt in receipts] == ["REMOVED", "REMOVED"]
    assert all(
        receipt.detail_style == receipt.label_style for receipt in receipts
    )
    assert initial_targets == [None]
    assert [
        checkpoint["command"]
        for checkpoint in store.list_checkpoints(owner.name)[:2]
    ] == ["remove", "remove"]

    first_undo = runner.invoke(app, ["undo"])
    assert first_undo.exit_code == 0, first_undo.output
    assert set(store.load_direct(owner.name).memories) == {second.uid}

    second_undo = runner.invoke(app, ["undo"])
    assert second_undo.exit_code == 0, second_undo.output
    assert set(store.load_direct(owner.name).memories) == {
        first.uid,
        second.uid,
    }


@pytest.mark.parametrize("command", ("delete", "remove"))
def test_explicit_batch_accepts_mixed_items_and_contexts_in_argv_order(
    isolated_store,
    command,
):
    store = MemoryStore()
    owner = ops.init("owner")
    first = ops.add(owner, "remove first")
    second = ops.add(owner, "remove second")
    store.create_context(owner)
    store.create_context(ops.init("victim-one"))
    store.create_context(ops.init("victim-two"))
    store.set_current(owner.name)

    result = runner.invoke(
        app,
        [
            command,
            first.uid[:8],
            "victim-one",
            second.uid[:8],
            "victim-two",
        ],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    assert result.output.count("Continue? [y/N]") == 1
    assert not store.context_exists("victim-one")
    assert not store.context_exists("victim-two")
    assert store.load_direct(owner.name).memories == {}
    assert [
        checkpoint["command"] for checkpoint in store.list_checkpoints(owner.name)[:2]
    ] == ["remove", "remove"]
    receipts = (
        f"Removed [{first.uid[:8]}]",
        "Deleted context 'victim-one'",
        f"Removed [{second.uid[:8]}]",
        "Deleted context 'victim-two'",
    )
    positions = tuple(result.output.index(receipt) for receipt in receipts)
    assert positions == tuple(sorted(positions))


def test_explicit_batch_scopes_every_item_selector_with_context_option(
    isolated_store,
):
    store = MemoryStore()
    owner = ops.init("owner")
    first = ops.add(owner, "remove first")
    second = ops.add(owner, "remove second")
    store.create_context(owner)

    result = runner.invoke(
        app,
        [
            "remove",
            first.uid[:8],
            second.uid[:8],
            "--context",
            owner.name,
        ],
    )

    assert result.exit_code == 0, result.output
    assert store.load_direct(owner.name).memories == {}


def test_explicit_batch_preflights_every_selector_before_first_change(
    isolated_store,
):
    store = MemoryStore()
    owner = ops.init("owner")
    memory = ops.add(owner, "keep when a later selector is invalid")
    store.create_context(owner)
    store.set_current(owner.name)

    result = runner.invoke(
        app,
        ["remove", memory.uid[:8], "missing-selector"],
    )

    assert result.exit_code == 1
    assert "No Context or direct item matches 'missing-selector'" in result.stderr
    assert memory.uid in store.load_direct(owner.name).memories
    assert store.list_checkpoints(owner.name) == []


def test_explicit_batch_rejects_duplicate_targets_before_first_change(
    isolated_store,
):
    store = MemoryStore()
    owner = ops.init("owner")
    memory = ops.add(owner, "keep when selected twice")
    store.create_context(owner)

    result = runner.invoke(
        app,
        ["remove", memory.uid[:8], memory.uid],
    )

    assert result.exit_code == 1
    assert "resolve to the same deletion target" in result.stderr
    assert memory.uid in store.load_direct(owner.name).memories
    assert store.list_checkpoints(owner.name) == []


def test_explicit_batch_rejects_context_and_its_direct_item_before_change(
    isolated_store,
):
    store = MemoryStore()
    owner = ops.init("owner")
    memory = ops.add(owner, "keep with its owner")
    store.create_context(owner)

    result = runner.invoke(
        app,
        ["remove", memory.uid[:8], owner.name],
        input="y\n",
    )

    assert result.exit_code == 1
    assert "selects Context 'owner' and direct item" in result.stderr
    assert store.context_exists(owner.name)
    assert memory.uid in store.load_direct(owner.name).memories
    assert store.list_checkpoints(owner.name) == []


def test_explicit_multi_context_cancel_is_read_only(isolated_store):
    store = MemoryStore()
    store.create_context(ops.init("victim-one"))
    store.create_context(ops.init("victim-two"))

    result = runner.invoke(
        app,
        ["delete", "victim-one", "victim-two"],
        input="n\n",
    )

    assert result.exit_code == 1
    assert result.output.count("Continue? [y/N]") == 1
    assert store.context_exists("victim-one")
    assert store.context_exists("victim-two")


def test_explicit_batch_deletes_lexical_parent_and_descendant_contexts(
    isolated_store,
):
    store = MemoryStore()
    store.create_context(ops.init("tree"))
    store.create_context(ops.init("tree/child"))

    result = runner.invoke(
        app,
        ["delete", "tree", "tree/child", "--force"],
    )

    assert result.exit_code == 0, result.output
    assert not store.context_exists("tree")
    assert not store.context_exists("tree/child")


def test_explicit_batch_resolves_every_relative_context_from_one_snapshot(
    isolated_store,
):
    store = MemoryStore()
    store.create_context(ops.init("project/one"))
    store.create_context(ops.init("project/two"))
    store.set_current("project/one")

    result = runner.invoke(
        app,
        ["delete", ".", "../two", "--force"],
    )

    assert result.exit_code == 0, result.output
    assert not store.context_exists("project/one")
    assert not store.context_exists("project/two")


def test_explicit_batch_revalidates_every_context_after_shared_approval(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    first = ops.init("victim-one")
    second = ops.init("victim-two")
    store.create_context(first)
    store.create_context(second)

    def replace_second_during_approval(*_args, **_kwargs):
        store.delete(second.name)
        replacement = ops.init(second.name)
        ops.add(replacement, "replacement survives")
        store.create_context(replacement)
        return True

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.delete.command.typer.confirm",
        replace_second_during_approval,
    )

    result = runner.invoke(
        app,
        ["delete", first.name, second.name],
    )

    assert result.exit_code == 1
    assert "changed after deletion was reviewed" in result.stderr
    assert store.context_exists(first.name)
    assert store.context_exists(second.name)
    assert [item.content for item in store.load_direct(second.name).iter_items()] == [
        "replacement survives"
    ]


def test_picker_item_failure_stays_in_footer_without_normal_output(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    owner = ops.init("owner")
    memory = ops.add(owner, "keep me")
    store.create_context(owner)
    store.set_current(owner.name)
    receipts = []

    def choose(*_args, **kwargs):
        receipts.append(
            kwargs["nested_accept_handler"](
                owner.name,
                "missing-item-uid",
            )
        )
        return None

    monkeypatch.setattr("memcommit.adapters.console.commands.delete.command.choose_context", choose)

    result = runner.invoke(app, ["remove"])

    assert result.exit_code == 0, result.output
    assert result.output == ""
    assert receipts[0].label == "DELETE FAILED"
    assert memory.uid in store.load_direct(owner.name).memories
