"""Ownership and compatibility paths for direct-Memory Copy and Move."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_copy_and_move_share_the_canonical_application_and_runtime() -> None:
    legacy_application = importlib.import_module(
        "memcommit.application.operations.memory_transfer.application"
    )
    canonical_application = importlib.import_module(
        "memcommit.application.operations.memory_transfer.application"
    )
    legacy_runtime = importlib.import_module("memcommit.application.operations.memory_transfer.runtime")
    canonical_runtime = importlib.import_module(
        "memcommit.application.operations.memory_transfer.runtime"
    )

    assert legacy_application is canonical_application
    assert (
        legacy_application.CopyMemoriesRequest
        is canonical_application.CopyMemoriesRequest
    )
    assert (
        legacy_application.MoveMemoriesRequest
        is canonical_application.MoveMemoriesRequest
    )
    assert legacy_application.run_copy is canonical_application.run_copy
    assert legacy_application.run_move is canonical_application.run_move
    assert legacy_runtime is canonical_runtime
    assert (
        legacy_runtime.MemoryStoreMemoryTransferPort
        is canonical_runtime.MemoryStoreMemoryTransferPort
    )


def test_memory_transfer_package_import_is_lazy() -> None:
    source = """
import sys
import memcommit.application.operations.memory_transfer

assert "memcommit.application.operations.memory_transfer.application" not in sys.modules
assert "memcommit.application.operations.memory_transfer.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_branch_remains_a_separate_context_creation_operation() -> None:
    path = REPOSITORY_ROOT / "src/memcommit/adapters/console/commands/branch/command.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    imports.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    assert not any(
        module == "memcommit.application.operations.memory_transfer"
        or module.startswith("memcommit.application.operations.memory_transfer.")
        for module in imports
    )
