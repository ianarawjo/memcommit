"""Plain Add CLI routes over the terminal-independent application."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.commands.help.command import COMMAND_FORMS
from memcommit.persistence.store import MemoryStore


runner = CliRunner()


def test_cli_positional_values_add_one_ordered_batch(isolated_store) -> None:
    store = MemoryStore()
    context = ops.init("target")
    store.save(context)
    store.set_current(context.name)
    before = len(store.list_checkpoints("target"))

    result = runner.invoke(
        app,
        ["add", "First", "Second\nline"],
    )

    assert result.exit_code == 0, result.output
    added = list(store.load_direct("target").memories.values())
    assert [memory.content for memory in added] == [
        "First",
        "Second\nline",
    ]
    checkpoints = store.list_checkpoints("target")
    assert len(checkpoints) == before + 1
    assert checkpoints[0]["args"]["count"] == 2
    assert checkpoints[0]["args"]["contents"] == ["First", "Second\nline"]
    assert checkpoints[0]["args"]["memory_uids"] == [memory.uid for memory in added]
    assert "Added 2 Memories to 'target'." in result.output
    assert f"  [{added[0].uid[:8]}] First" in result.output
    assert f"  [{added[1].uid[:8]}] Second\\nline" in result.output
    assert f"Checkpoint [{checkpoints[0]['uid'][:8]}]." in result.output


def test_cli_treats_each_positional_value_as_one_memory(isolated_store) -> None:
    store = MemoryStore()
    context = ops.init("target")
    store.save(context)
    store.set_current(context.name)

    result = runner.invoke(app, ["add", "my", "name", "is"])

    assert result.exit_code == 0, result.output
    assert [
        memory.content for memory in store.load_direct("target").memories.values()
    ] == ["my", "name", "is"]


@pytest.mark.parametrize(
    "values",
    [
        ("",),
        ("   ",),
        ("valid", "\t"),
    ],
)
def test_cli_rejects_blank_positional_memories_before_mutation(
    isolated_store,
    values: tuple[str, ...],
) -> None:
    store = MemoryStore()
    context = ops.init("target")
    store.save(context)
    store.set_current(context.name)
    checkpoint_count = len(store.list_checkpoints("target"))

    result = runner.invoke(app, ["add", *values])

    assert result.exit_code == 1
    assert "must contain nonblank text" in result.output
    assert not store.load_direct("target").memories
    assert len(store.list_checkpoints("target")) == checkpoint_count


@pytest.mark.parametrize("removed_option", ["--memory", "-m", "--input", "-i"])
def test_cli_no_longer_exposes_redundant_or_file_input_options(
    isolated_store,
    removed_option: str,
) -> None:
    result = runner.invoke(app, ["add", removed_option, "value"])

    assert result.exit_code == 2
    assert "No such option" in result.output
    assert not isolated_store.exists()


def test_cli_without_input_requires_terminal_before_opening_store(
    isolated_store,
) -> None:
    result = runner.invoke(app, ["add"])

    assert result.exit_code == 1
    assert "Interactive Add requires a TTY" in result.output
    assert "Pass positional MEMORY values or --paste" in result.output
    assert not isolated_store.exists()


def test_cli_to_names_the_explicit_add_target(isolated_store) -> None:
    store = MemoryStore()
    current = ops.init("current")
    target = ops.init("target")
    store.save(current)
    store.save(target)
    store.set_current(current.name)

    result = runner.invoke(app, ["add", "Directed Memory", "--to", "target"])

    assert result.exit_code == 0, result.output
    assert not store.load_direct("current").memories
    added = list(store.load_direct("target").memories.values())
    assert [memory.content for memory in added] == ["Directed Memory"]
    assert "Added 1 Memory to 'target'." in result.output
    assert f"  [{added[0].uid[:8]}] Directed Memory" in result.output
    assert "Checkpoint [" in result.output


def test_cli_positional_batch_uses_one_explicit_target(isolated_store) -> None:
    store = MemoryStore()
    current = ops.init("current")
    target = ops.init("target")
    store.save(current)
    store.save(target)
    store.set_current(current.name)

    result = runner.invoke(app, ["add", "First", "Second", "--to", "target"])

    assert result.exit_code == 0, result.output
    assert not store.load_direct("current").memories
    assert [
        memory.content for memory in store.load_direct("target").memories.values()
    ] == ["First", "Second"]


@pytest.mark.parametrize(
    "target_arguments",
    (
        ("--to", "first", "--context", "second"),
        ("-c", "first", "-c", "second"),
    ),
)
def test_cli_target_aliases_use_the_last_value_and_receipt_names_it(
    isolated_store,
    target_arguments: tuple[str, ...],
) -> None:
    store = MemoryStore()
    first = ops.init("first")
    second = ops.init("second")
    store.save(first)
    store.save(second)
    store.set_current(first.name)

    result = runner.invoke(
        app,
        ["add", "Added once", *target_arguments],
    )

    assert result.exit_code == 0, result.output
    assert not store.load_direct("first").memories
    added = list(store.load_direct("second").memories.values())
    assert [memory.content for memory in added] == ["Added once"]
    assert "Added 1 Memory to 'second'." in result.output
    assert f"  [{added[0].uid[:8]}] Added once" in result.output


def test_add_help_groups_target_context_aliases() -> None:
    result = runner.invoke(app, ["add", "-h"])

    assert result.exit_code == 0
    assert result.output.index("--to") < result.output.index("--context")
    assert "-c" in result.output
    assert "Target Context to receive the Memories;" in result.output
    assert "--context/-c are compatibility aliases" in result.output
    assert "[MEMORY]..." in result.output
    assert "--memory" not in result.output
    assert "--input" not in result.output


def test_edit_and_remove_keep_context_c_without_to() -> None:
    for command in ("edit", "remove"):
        result = runner.invoke(app, [command, "-h"])

        assert result.exit_code == 0
        assert "--context" in result.output
        assert "-c" in result.output
        assert "--to" not in result.output

        rejected = runner.invoke(app, [command, "--to", "target"])
        assert rejected.exit_code == 2
        assert "No such option: --to" in rejected.output


def test_interactive_help_uses_to_for_explicit_add_targets() -> None:
    explicit_target_forms = tuple(
        form for form in COMMAND_FORMS["add"] if "[target_context]" in form
    )

    assert explicit_target_forms
    assert all("--to [target_context]" in form for form in explicit_target_forms)
    assert not any("--context" in form for form in explicit_target_forms)


def test_interactive_close_reports_each_saved_context_without_cancellation(
    isolated_store, monkeypatch
):
    import memcommit.adapters.console.commands.add.command as command
    from memcommit.application.operations.add.application import AddRequest

    store = MemoryStore()
    for name in ("first", "second"):
        store.save(ops.init(name))
    store.set_current("first")
    monkeypatch.setattr(
        command, "require_interactive_terminal", lambda *args, **kwargs: None
    )

    def workbench(*, setup, execute, load_memories, **kwargs):
        results = []
        for name in ("first", "second"):
            results.append(
                execute(AddRequest(context_locator=name, contents=(f"For {name}",)))
            )
            assert load_memories(name)[-1].content == f"For {name}"
        return tuple(results)

    monkeypatch.setattr(command, "run_add_workbench", workbench)
    result = runner.invoke(app, ["add"])
    assert result.exit_code == 0, result.output
    assert "Added 1 Memory to 'first'." in result.output
    assert "Added 1 Memory to 'second'." in result.output
    assert "cancelled" not in result.output
    assert store.current_context_name() == "first"
