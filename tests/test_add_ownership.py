"""Ownership and compatibility paths for exact user-supplied Add."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_add_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.add

assert "memcommit.application.operations.add.application" not in sys.modules
assert "memcommit.application.operations.add.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_add_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/_operations/add.py",
        "src/memcommit/adapters/console/commands/add/command.py",
        "src/memcommit/adapters/console/commands/add/receipt.py",
        "src/memcommit/adapters/console/commands/add/workbench/screen.py",
        "src/memcommit/application/operations/add/runtime.py",
    )

    for relative_path in relative_paths:
        path = REPOSITORY_ROOT / relative_path
        source = path.read_text(encoding="utf-8")
        assert "from memcommit.add_application import" not in source
        assert "from memcommit.add_runtime import" not in source


def test_add_presenters_are_colocated_with_their_command() -> None:
    command = REPOSITORY_ROOT / (
        "src/memcommit/adapters/console/commands/add/command.py"
    )
    receipt = REPOSITORY_ROOT / (
        "src/memcommit/adapters/console/commands/add/receipt.py"
    )
    workbench = REPOSITORY_ROOT / (
        "src/memcommit/adapters/console/commands/add/workbench/screen.py"
    )
    retired = tuple(
        REPOSITORY_ROOT / path
        for path in (
            "src/memcommit/adapters/interfaces/cli/add.py",
            "src/memcommit/adapters/interfaces/tui/operations/add/__init__.py",
            "src/memcommit/adapters/interfaces/tui/operations/add/model.py",
            "src/memcommit/adapters/interfaces/tui/operations/add/screen.py",
        )
    )

    assert receipt.is_file()
    assert workbench.is_file()
    assert all(not path.exists() for path in retired)
    assert (
        "from memcommit.adapters.console.commands.add.receipt import render_add_receipt"
    ) in command.read_text(encoding="utf-8")
    assert "memcommit.adapters.console.commands.add.workbench" in command.read_text(
        encoding="utf-8"
    )


def test_exact_add_does_not_absorb_semantic_result_memorization() -> None:
    operation_root = REPOSITORY_ROOT / "src/memcommit/application/operations/add"
    assert not (operation_root / "semantic_runtime.py").exists()

    for relative_path in (
        "src/memcommit/application/operations/add/application.py",
        "src/memcommit/application/operations/add/runtime.py",
    ):
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "memcommit.semantic_add_runtime" not in source
        assert "semantic_result_memorization" not in source
        assert "memcommit.makemore_add_runtime" not in source
        assert "memcommit.application.operations.makemore.add_runtime" not in source
