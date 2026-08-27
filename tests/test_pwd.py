"""Application, runtime, and CLI contracts for ``mem pwd``."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from typer.testing import CliRunner

import memcommit.application.operations.pwd.application as current_context_application
import memcommit.application.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.application.operations.pwd.application import (
    CurrentContextError,
    NoCurrentContextError,
    get_current_context,
)
from memcommit.application.operations.pwd.runtime import read_current_context
from memcommit.persistence.store import MemoryStore


runner = CliRunner(mix_stderr=False)


class _StaticCurrentContextReader:
    def __init__(self, name):
        self.name = name
        self.calls = 0

    def current_context_name(self):
        self.calls += 1
        return self.name


def test_application_returns_one_typed_current_context_result():
    reader = _StaticCurrentContextReader("task-1/participant")

    result = get_current_context(reader)

    assert result.context_name == "task-1/participant"
    assert reader.calls == 1


def test_application_rejects_missing_or_invalid_current_context():
    with pytest.raises(NoCurrentContextError, match="No current Context"):
        get_current_context(_StaticCurrentContextReader(None))

    for invalid in ("", 7):
        with pytest.raises(CurrentContextError, match="state is invalid"):
            get_current_context(_StaticCurrentContextReader(invalid))


def test_application_has_no_store_command_or_terminal_imports():
    source = Path(current_context_application.__file__).read_text(encoding="utf-8")
    imported: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)

    assert not any(
        name == "typer"
        or name.startswith("prompt_toolkit")
        or name.startswith("memcommit.adapters.console.commands")
        or name == "memcommit.store"
        for name in imported
    )


def test_runtime_reads_current_pointer_without_terminal_output(
    isolated_store,
    capsys,
):
    store = MemoryStore()
    context = ops.init("task-1/participant")
    store.save(context)
    store.set_current(context.name)

    result = read_current_context(store)

    assert result.context_name == context.name
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_pwd_prints_only_the_canonical_current_context_name(isolated_store):
    store = MemoryStore()
    context = ops.init("task-1/participant")
    store.save(context)
    store.set_current(context.name)

    result = runner.invoke(app, ["pwd"])

    assert result.exit_code == 0, result.stderr
    assert result.stdout == "task-1/participant\n"
    assert result.stderr == ""


def test_pwd_reports_unset_state_without_creating_a_store(isolated_store):
    assert not isolated_store.exists()

    result = runner.invoke(app, ["pwd"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "No current Context" in result.stderr
    assert not isolated_store.exists()


def test_pwd_reports_a_virtual_current_pointer_without_loading_it(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    local = ops.init("local")
    store.save(local)
    store.set_current(local.name)
    store.set_current_virtual_context_if(local.name, "campus-wiki/public")

    def forbidden_load(*args, **kwargs):
        raise AssertionError("pwd must not load or authorize Context contents")

    monkeypatch.setattr(MemoryStore, "load", forbidden_load)
    monkeypatch.setattr(MemoryStore, "load_direct", forbidden_load)

    result = runner.invoke(app, ["pwd"])

    assert result.exit_code == 0, result.stderr
    assert result.stdout == "campus-wiki/public\n"
    assert result.stderr == ""


def test_pwd_help_describes_the_orientation_only_contract():
    result = runner.invoke(app, ["pwd", "--help"])

    assert result.exit_code == 0, result.output
    assert "current canonical Context name" in result.output
    assert "OPTIONS" in result.output
