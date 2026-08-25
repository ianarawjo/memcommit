"""Ownership checks for the Clear operation."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys

import pytest

from memcommit.operations.clear.application import ClearRequest, ClearResult


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_clear_request_and_result_are_terminal_independent() -> None:
    request = ClearRequest(context_locator="work/source", recursive=True)
    result = ClearResult(
        context_name="work/source",
        recursive=True,
        item_count=3,
        scope_count=2,
        changed_context_count=1,
    )
    assert request.recursive
    assert result.changed

    with pytest.raises(ValueError, match="nonempty"):
        ClearRequest(context_locator="")


def test_clear_command_delegates_behavior_to_operation_runtime() -> None:
    path = REPOSITORY_ROOT / "memcommit/commands/clear.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert "memcommit.operations.clear.application" in imports
    assert "memcommit.operations.clear.runtime" in imports
    assert "memcommit.authority.access" not in imports
    assert "memcommit.context_targeting.readable_catalog" not in imports
    assert "memcommit.context_targeting.resolution" not in imports


def test_clear_operation_has_no_terminal_dependency() -> None:
    for relative_path in (
        "memcommit/operations/clear/application.py",
        "memcommit/operations/clear/runtime.py",
    ):
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "import typer" not in source
        assert "memcommit.commands" not in source


def test_clear_operation_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.operations.clear

assert not [
    name
    for name in sys.modules
    if name.startswith("memcommit.operations.clear.")
]
"""
    subprocess.run([sys.executable, "-c", program], cwd=REPOSITORY_ROOT, check=True)
