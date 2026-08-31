"""Plain Add CLI routes over the terminal-independent application."""

from __future__ import annotations

from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.commands.system_study_tools.help.command import COMMAND_FORMS
from memcommit.persistence.store import MemoryStore


runner = CliRunner()


def test_cli_repeatable_memory_option_adds_one_explicit_batch(isolated_store) -> None:
    store = MemoryStore()
    context = ops.init("target")
    store.save(context)
    store.set_current(context.name)
    before = len(store.list_checkpoints("target"))

    result = runner.invoke(
        app,
        ["add", "--memory", "First", "--memory", "Second\nline"],
    )

    assert result.exit_code == 0, result.output
    assert "Added 2 Memories" in result.output
    assert [
        memory.content for memory in store.load_direct("target").memories.values()
    ] == [
        "First",
        "Second\nline",
    ]
    assert len(store.list_checkpoints("target")) == before + 1


def test_cli_without_source_retains_noninteractive_error(isolated_store) -> None:
    result = runner.invoke(app, ["add"])

    assert result.exit_code == 1
    assert "provide exactly one" in result.output
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
    assert [
        memory.content for memory in store.load_direct("target").memories.values()
    ] == ["Directed Memory"]


def test_cli_rejects_duplicate_add_target_spellings_before_store_access(
    isolated_store,
) -> None:
    result = runner.invoke(
        app,
        [
            "add",
            "Must not be added",
            "--to",
            "first",
            "--context",
            "second",
        ],
    )

    assert result.exit_code == 1
    assert "Add target was supplied with more than one option" in result.output
    assert "--to and --context/-c" in result.output
    assert not isolated_store.exists()


def test_add_help_prefers_to_and_retains_context_compatibility() -> None:
    result = runner.invoke(app, ["add", "-h"])

    assert result.exit_code == 0
    assert result.output.index("--to") < result.output.index("--context")
    assert "Compatibility spelling for the Add target" in result.output
    assert "equivalent to --to" in result.output


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
    explicit_target_forms = COMMAND_FORMS["add"][5:]

    assert explicit_target_forms
    assert all("--to [target_context]" in form for form in explicit_target_forms)
    assert not any("--context" in form for form in explicit_target_forms)
