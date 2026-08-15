"""Plain Add CLI routes over the terminal-independent application."""

from __future__ import annotations

from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.store import MemoryStore


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
