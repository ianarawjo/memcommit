from __future__ import annotations

import ast
import importlib
from pathlib import Path
import subprocess
import sys

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LEGACY_MODULE = "memcommit.commands.ground.workspace_picker"
CANONICAL_MODULE = "memcommit.interfaces.tui.operations.ground_workspace.picker"


@pytest.mark.parametrize(
    "first_name,second_name",
    ((LEGACY_MODULE, CANONICAL_MODULE), (CANONICAL_MODULE, LEGACY_MODULE)),
    ids=("old-first", "new-first"),
)
def test_picker_module_identity_is_independent_of_import_order(
    first_name: str,
    second_name: str,
) -> None:
    source = f"""
import importlib
import sys

first = importlib.import_module({first_name!r})
second = importlib.import_module({second_name!r})
legacy = importlib.import_module({LEGACY_MODULE!r})
canonical = importlib.import_module({CANONICAL_MODULE!r})

assert first is second
assert legacy is canonical
assert sys.modules[{LEGACY_MODULE!r}] is canonical
assert sys.modules[{CANONICAL_MODULE!r}] is canonical
"""

    subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_legacy_picker_exports_the_canonical_objects() -> None:
    canonical = importlib.import_module(CANONICAL_MODULE)
    legacy = importlib.import_module(LEGACY_MODULE)

    assert legacy is canonical
    assert legacy.__all__ == canonical.__all__
    assert all(
        getattr(legacy, name) is getattr(canonical, name) for name in canonical.__all__
    )


def test_legacy_picker_facade_defines_no_behavior() -> None:
    facade_path = REPOSITORY_ROOT / "src/memcommit/commands/ground/workspace_picker.py"
    tree = ast.parse(facade_path.read_text(encoding="utf-8"))

    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for node in ast.walk(tree)
    )
    assert any(
        isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Subscript)
            and isinstance(target.value, ast.Attribute)
            and isinstance(target.value.value, ast.Name)
            and target.value.value.id == "sys"
            and target.value.attr == "modules"
            for target in node.targets
        )
        for node in tree.body
    )


def test_ground_command_imports_the_interface_owner() -> None:
    command_path = REPOSITORY_ROOT / "src/memcommit/commands/ground/command.py"
    tree = ast.parse(command_path.read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert CANONICAL_MODULE in imported_modules
    assert LEGACY_MODULE not in imported_modules
