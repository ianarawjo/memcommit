"""Ownership and compatibility paths for direct-Memory Copy and Move."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_copy_and_move_own_separate_application_entrypoints() -> None:
    copy_application = importlib.import_module(
        "memcommit.application.operations.copy.application"
    )
    move_application = importlib.import_module(
        "memcommit.application.operations.direct_changes.move.application"
    )
    shared_contracts = importlib.import_module(
        "memcommit.application.operations.copy_and_move.application"
    )
    copy_runtime = importlib.import_module("memcommit.application.operations.copy.runtime")
    move_runtime = importlib.import_module("memcommit.application.operations.direct_changes.move.runtime")

    assert copy_application.run_copy.__module__ == copy_application.__name__
    assert move_application.run_move.__module__ == move_application.__name__
    assert copy_application.CopyMemoriesRequest is shared_contracts.CopyMemoriesRequest
    assert move_application.MoveMemoriesRequest is shared_contracts.MoveMemoriesRequest
    assert copy_runtime.MemoryStoreCopyPort.__module__ == copy_runtime.__name__
    assert move_runtime.MemoryStoreMovePort.__module__ == move_runtime.__name__
    assert not hasattr(shared_contracts, "run_copy")
    assert not hasattr(shared_contracts, "run_move")


def test_copy_and_move_shared_package_import_is_lazy() -> None:
    source = """
import sys
import memcommit.application.operations.copy_and_move

assert "memcommit.application.operations.copy_and_move.application" not in sys.modules
assert "memcommit.application.operations.copy_and_move.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_copy_and_move_own_commands_while_transfer_mechanics_stay_coordinated() -> None:
    console = REPOSITORY_ROOT / "src/memcommit/adapters/console"
    interfaces = REPOSITORY_ROOT / "src/memcommit/adapters/interfaces"

    for command in ("copy", "move"):
        root = console / "commands" / (
            Path(command)
            if command == "copy"
            else Path("direct_changes") / command
        )
        assert (root / "__init__.py").is_file()
        assert (root / "command.py").is_file()
        assert (root / "setup.py").is_file()
        assert (root / "receipt.py").is_file()
    coordination = console / "coordination" / "copy_and_move"
    assert {path.name for path in coordination.glob("*.py")} == {
        "__init__.py",
        "arguments.py",
        "model.py",
        "receipt.py",
    }
    assert (console / "terminal" / "components" / "copy_and_move.py").is_file()
    assert not (console / "shared").exists()
    assert not (interfaces / "cli" / "copy_and_move.py").exists()
    assert not tuple(
        (interfaces / "tui" / "operations" / "copy_and_move").glob("*.py")
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
        module == "memcommit.application.operations.copy_and_move"
        or module.startswith("memcommit.application.operations.copy_and_move.")
        for module in imports
    )
