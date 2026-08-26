"""Ownership and compatibility paths for direct-Memory Copy and Move."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import pickle
import subprocess
import sys

import pytest

from tests.legacy_submodule_assertions import (
    assert_legacy_root_submodule_is_centralized,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODULE_PAIRS = (
    (
        "memcommit.memory_transfer_application",
        "memcommit.operations.memory_transfer.application",
    ),
    (
        "memcommit.memory_transfer_runtime",
        "memcommit.operations.memory_transfer.runtime",
    ),
)


@pytest.mark.parametrize("legacy_name,canonical_name", MODULE_PAIRS)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_memory_transfer_module_identity_is_independent_of_import_order(
    legacy_name: str,
    canonical_name: str,
    legacy_first: bool,
) -> None:
    first_name, second_name = (
        (legacy_name, canonical_name) if legacy_first else (canonical_name, legacy_name)
    )
    source = f"""
import importlib
import sys

first = importlib.import_module({first_name!r})
second = importlib.import_module({second_name!r})
legacy = importlib.import_module({legacy_name!r})
canonical = importlib.import_module({canonical_name!r})

assert first is second
assert legacy is canonical
assert sys.modules[{legacy_name!r}] is canonical
assert sys.modules[{canonical_name!r}] is canonical
"""

    subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_copy_and_move_share_the_canonical_application_and_runtime() -> None:
    legacy_application = importlib.import_module(
        "memcommit.memory_transfer_application"
    )
    canonical_application = importlib.import_module(
        "memcommit.operations.memory_transfer.application"
    )
    legacy_runtime = importlib.import_module("memcommit.memory_transfer_runtime")
    canonical_runtime = importlib.import_module(
        "memcommit.operations.memory_transfer.runtime"
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


@pytest.mark.parametrize(
    "relative_path",
    (
        "memcommit/memory_transfer_application.py",
        "memcommit/memory_transfer_runtime.py",
    ),
)
def test_memory_transfer_legacy_facades_define_no_behavior(
    relative_path: str,
) -> None:
    assert_legacy_root_submodule_is_centralized(relative_path)


def test_memory_transfer_package_import_is_lazy() -> None:
    source = """
import sys
import memcommit.operations.memory_transfer

assert "memcommit.operations.memory_transfer.application" not in sys.modules
assert "memcommit.operations.memory_transfer.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_pre_relocation_copy_request_global_loads_through_legacy_alias() -> None:
    canonical = importlib.import_module(
        "memcommit.operations.memory_transfer.application"
    )

    restored = pickle.loads(
        b"cmemcommit.memory_transfer_application\nCopyMemoriesRequest\n."
    )

    assert restored is canonical.CopyMemoriesRequest


def test_branch_remains_a_separate_context_creation_operation() -> None:
    path = REPOSITORY_ROOT / "memcommit/commands/branch/command.py"
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
        module == "memcommit.operations.memory_transfer"
        or module.startswith("memcommit.operations.memory_transfer.")
        for module in imports
    )
