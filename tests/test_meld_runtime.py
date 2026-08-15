"""Infrastructure-boundary checks for production Meld execution."""

from __future__ import annotations

import ast
from pathlib import Path

import memcommit.meld_runtime as meld_runtime


def test_meld_runtime_has_no_terminal_or_command_dependencies():
    source = Path(meld_runtime.__file__).read_text(encoding="utf-8")
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
