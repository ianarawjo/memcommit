"""Ownership and compatibility paths for deterministic Resolve."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_resolve_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.resolve

assert "memcommit.application.operations.resolve.application" not in sys.modules
assert "memcommit.application.operations.resolve.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_resolve_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/resolve.py",
        "src/memcommit/adapters/python_api/_operations/resolve.py",
        "src/memcommit/adapters/console/commands/resolve/command.py",
        "src/memcommit/adapters/console/commands/resolve/analysis.py",
        "src/memcommit/adapters/console/commands/resolve/receipt.py",
        "src/memcommit/adapters/console/commands/resolve/workbench/presentation.py",
        "src/memcommit/adapters/console/commands/resolve/workbench/screen.py",
        "src/memcommit/adapters/console/commands/find_conflicts/resolve_handoff.py",
        "src/memcommit/adapters/console/commands/find_conflicts/command.py",
        "src/memcommit/adapters/console/commands/impact/process_local.py",
        "src/memcommit/application/reviewing/quality/handoff.py",
        "src/memcommit/application/operations/resolve/semantic.py",
        "src/memcommit/application/operations/resolve/targeting.py",
        "src/memcommit/application/operations/resolve/runtime.py",
    )

    for relative_path in relative_paths:
        path = REPOSITORY_ROOT / relative_path
        source = path.read_text(encoding="utf-8")
        assert "from memcommit.resolve_application import" not in source
        assert "from memcommit.resolve_runtime import" not in source


def test_resolve_console_owns_analysis_receipt_and_workbench_without_facades() -> None:
    command_root = (
        REPOSITORY_ROOT / "src/memcommit/adapters/console/commands/resolve"
    )
    retired_tui_root = (
        REPOSITORY_ROOT / "src/memcommit/adapters/interfaces/tui/operations/resolve"
    )

    assert (command_root / "analysis.py").is_file()
    assert (command_root / "receipt.py").is_file()
    assert (command_root / "workbench/presentation.py").is_file()
    assert (command_root / "workbench/screen.py").is_file()
    assert not tuple(retired_tui_root.glob("*.py"))
    assert not (
        REPOSITORY_ROOT / "src/memcommit/adapters/interfaces/cli/resolve.py"
    ).exists()
