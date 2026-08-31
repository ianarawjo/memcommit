"""Ownership and compatibility paths for Chunk."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_ops_chunk_is_a_thin_operation_compatibility_adapter() -> None:
    path = REPOSITORY_ROOT / "src/memcommit/application/capabilities/ops.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    definitions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "chunk"
    ]

    assert len(definitions) == 1
    source = ast.get_source_segment(path.read_text(encoding="utf-8"), definitions[0])
    assert source is not None
    assert "memcommit.application.operations.chunk.application" in source
    assert "chunk_content" not in source


def test_chunk_command_uses_only_operation_owned_chunk_behavior() -> None:
    path = REPOSITORY_ROOT / "src/memcommit/adapters/console/commands/chunk/command.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert "memcommit.application.operations.chunk.application" in imports
    assert "memcommit.application.operations.chunk.domain" in imports
    assert "memcommit.application.operations.chunk.runtime" in imports
    assert "memcommit.chunking" not in imports


def test_chunk_operation_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.chunk

assert not [
    name
    for name in sys.modules
    if name.startswith("memcommit.application.operations.chunk.")
]
"""
    subprocess.run([sys.executable, "-c", program], cwd=REPOSITORY_ROOT, check=True)


def test_chunk_domain_and_application_have_no_terminal_dependency() -> None:
    for relative_path in (
        "src/memcommit/application/operations/chunk/domain.py",
        "src/memcommit/application/operations/chunk/application.py",
    ):
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "import typer" not in source
        assert "memcommit.adapters.console.commands" not in source
