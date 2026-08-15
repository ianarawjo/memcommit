"""Infrastructure-boundary checks for production Meld execution."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import memcommit.meld_assessment_application as meld_assessment_application
import memcommit.meld_runtime as meld_runtime
import memcommit.meld_session_application as meld_session_application


@pytest.mark.parametrize(
    "module",
    (
        meld_assessment_application,
        meld_session_application,
        meld_runtime,
    ),
)
def test_meld_execution_modules_have_no_terminal_or_command_dependencies(module):
    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)

    assert tuple(
        name
        for name in imported
        if name == "typer"
        or name.startswith("prompt_toolkit")
        or name.startswith("memcommit.commands")
    ) == ()
