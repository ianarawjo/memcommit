"""Ownership and compatibility paths for the Merge operation slice."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_merge_package_import_is_lazy() -> None:
    source = """
import sys
import memcommit.application.operations.merge

assert "memcommit.application.operations.merge.application" not in sys.modules
assert "memcommit.application.operations.merge.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_merge_command_owns_setup_resolution_receipt_and_workbench() -> None:
    command_root = REPOSITORY_ROOT / "src/memcommit/adapters/console/commands/merge"

    assert (command_root / "setup.py").is_file()
    assert (command_root / "resolution.py").is_file()
    assert (command_root / "receipt.py").is_file()
    assert (command_root / "workbench/review.py").is_file()
    assert (command_root / "workbench/conflicts.py").is_file()
    assert not (
        REPOSITORY_ROOT / "src/memcommit/adapters/interfaces/cli/merge.py"
    ).exists()
    assert not tuple(
        (
            REPOSITORY_ROOT / "src/memcommit/adapters/interfaces/tui/operations/merge"
        ).glob("*.py")
    )


def test_merge_command_does_not_import_removed_interface_facades() -> None:
    command_root = REPOSITORY_ROOT / "src/memcommit/adapters/console/commands/merge"
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(command_root.rglob("*.py"))
    )

    assert "memcommit.adapters.interfaces.cli.merge" not in source
    assert "memcommit.adapters.interfaces.tui.operations.merge" not in source
