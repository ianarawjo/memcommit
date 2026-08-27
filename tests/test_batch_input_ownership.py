"""Ownership contracts for line-oriented batch input."""

from __future__ import annotations

import ast
import importlib
import io
from pathlib import Path
import subprocess
import sys

import pytest


REPOSITORY_ROOT = Path(__file__).parents[1]
LEGACY_MODULE = "memcommit.adapters.console.commands.shared.batch_input"
OWNER_MODULE = "memcommit.adapters.interfaces.cli.batch_input"


@pytest.mark.parametrize(
    "first_name,second_name",
    ((LEGACY_MODULE, OWNER_MODULE), (OWNER_MODULE, LEGACY_MODULE)),
    ids=("old-first", "new-first"),
)
def test_batch_input_module_identity_is_independent_of_import_order(
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
assert sys.modules[{LEGACY_MODULE!r}] is canonical
assert sys.modules[{OWNER_MODULE!r}] is canonical
"""

    subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_legacy_batch_input_facade_defines_no_behavior() -> None:
    path = (
        REPOSITORY_ROOT
        / "src"
        / "memcommit"
        / "adapters"
        / "console"
        / "commands"
        / "shared"
        / "batch_input.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for node in ast.walk(tree)
    )


def test_legacy_monkeypatch_changes_canonical_stdin(monkeypatch) -> None:
    legacy = importlib.import_module(LEGACY_MODULE)
    canonical = importlib.import_module(OWNER_MODULE)
    patched_sys = type("PatchedSys", (), {"stdin": io.StringIO("one\r\ntwo\n")})

    monkeypatch.setattr(legacy, "sys", patched_sys)

    assert canonical.sys is patched_sys
    assert canonical.read_text_input("-") == "one\r\ntwo\n"


def test_add_and_edit_commands_import_the_interface_owner() -> None:
    for filename in ("add/command.py", "edit/command.py"):
        source = (
            REPOSITORY_ROOT
            / "src"
            / "memcommit"
            / "adapters"
            / "console"
            / "commands"
            / filename
        ).read_text(encoding="utf-8")
        assert "from memcommit.adapters.interfaces.cli.batch_input import" in source
        assert "from memcommit.adapters.console.commands.shared.batch_input import" not in source
