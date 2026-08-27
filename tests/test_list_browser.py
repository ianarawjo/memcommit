"""Stable terminal-output contracts for ``mem ls`` and ``mem contexts``."""

from __future__ import annotations

import inspect

from typer.testing import CliRunner

from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.commands.contexts import command as contexts
from memcommit.adapters.console.commands.list_memories import command as list_memories


runner = CliRunner()


def invoke(*args: str):
    return runner.invoke(app, list(args))


def test_ls_prints_only_the_resolved_direct_scope(isolated_store):
    invoke("init", "outside")
    invoke("init", "root")
    invoke("add", "root memory")
    invoke("init", "root/child")
    invoke("add", "child memory")
    invoke("switch", "root")

    result = invoke("ls")

    assert result.exit_code == 0
    assert "Context: root" in result.output
    assert "root/child" in result.output
    assert "root memory" in result.output
    assert "outside" not in result.output
    assert "child memory" not in result.output


def test_recursive_ls_prints_the_resolved_subtree_not_profile_siblings(
    isolated_store,
):
    invoke("init", "outside")
    invoke("init", "root")
    invoke("init", "root/child")
    invoke("add", "child memory")

    result = invoke("ls", "-R", "root")

    assert result.exit_code == 0
    assert "Context: root" in result.output
    assert "root/child" in result.output
    assert "child memory" in result.output
    assert "outside" not in result.output


def test_orientation_commands_do_not_depend_on_the_context_tui():
    for module in (contexts, list_memories):
        source = inspect.getsource(module)
        assert "context_targeting.tui" not in source
        assert "_interactive_terminal" not in source
