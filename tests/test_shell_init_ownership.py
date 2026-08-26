"""Ownership contracts for the shell-integration command adapter."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys

import pytest


REPOSITORY_ROOT = Path(__file__).parents[1]
LEGACY_MODULE = "memcommit.commands.shell_init.command"
OWNER_MODULE = "memcommit.interfaces.cli.shell_init"


@pytest.mark.parametrize(
    "first_name,second_name",
    ((LEGACY_MODULE, OWNER_MODULE), (OWNER_MODULE, LEGACY_MODULE)),
    ids=("old-first", "new-first"),
)
def test_shell_init_module_and_callable_identity_is_import_order_independent(
    first_name: str,
    second_name: str,
) -> None:
    source = f"""
import importlib
import sys

first = importlib.import_module({first_name!r})
second = importlib.import_module({second_name!r})
legacy = importlib.import_module({LEGACY_MODULE!r})
canonical = importlib.import_module({OWNER_MODULE!r})

assert first is second
assert legacy is canonical
assert legacy.cmd is canonical.cmd
assert legacy.render_zsh_init is canonical.render_zsh_init
assert sys.modules[{LEGACY_MODULE!r}] is canonical
assert sys.modules[{OWNER_MODULE!r}] is canonical
"""

    subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_legacy_shell_init_facade_defines_no_behavior() -> None:
    path = (
        REPOSITORY_ROOT
        / "memcommit"
        / "commands"
        / "shell_init"
        / "command.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for node in ast.walk(tree)
    )


def test_cli_registers_the_interface_owned_shell_init_command() -> None:
    path = REPOSITORY_ROOT / "memcommit" / "cli.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    interface_imports = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "memcommit.interfaces.cli"
        for alias in node.names
    }
    command_imports = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "memcommit.commands"
        for alias in node.names
    }

    assert "shell_init" in interface_imports
    assert "shell_init" not in command_imports

    from memcommit.cli import app
    from memcommit.interfaces.cli import shell_init

    registration = next(
        command for command in app.registered_commands if command.name == "shell-init"
    )
    assert registration.callback is shell_init.cmd
