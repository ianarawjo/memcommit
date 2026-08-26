"""Ownership checks for the read-only Contexts operation."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys

import pytest

from memcommit.operations.contexts.application import ContextCatalogEntry


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_context_catalog_entry_keeps_grant_metadata_typed() -> None:
    granted = ContextCatalogEntry(
        name="shared/reference",
        current=False,
        ownership="GRANT",
        portable_name=True,
        capabilities="READ · QUERY",
        authority_profile="research",
    )
    assert granted.authority_profile == "research"

    with pytest.raises(ValueError, match="require capabilities"):
        ContextCatalogEntry(
            name="shared/reference",
            current=False,
            ownership="GRANT",
            portable_name=True,
        )


def test_contexts_command_imports_the_operation_runtime() -> None:
    path = REPOSITORY_ROOT / "src/memcommit/commands/contexts/command.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert "memcommit.operations.contexts.application" in imports
    assert "memcommit.operations.contexts.runtime" in imports
    assert "memcommit.context_targeting.catalog" not in imports
    assert "memcommit.context_targeting.resolution" not in imports


def test_contexts_operation_has_no_terminal_dependency() -> None:
    for relative_path in (
        "src/memcommit/operations/contexts/application.py",
        "src/memcommit/operations/contexts/runtime.py",
    ):
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "import typer" not in source
        assert "memcommit.commands" not in source


def test_contexts_operation_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.operations.contexts

assert not [
    name
    for name in sys.modules
    if name.startswith("memcommit.operations.contexts.")
]
"""
    subprocess.run([sys.executable, "-c", program], cwd=REPOSITORY_ROOT, check=True)
