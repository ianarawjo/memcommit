"""Ownership and compatibility paths for selective Forget."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_forget_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.forget

assert "memcommit.application.operations.forget.application" not in sys.modules
assert "memcommit.application.operations.forget.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_forget_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/forget.py",
        "src/memcommit/adapters/python_api/_operations/forget.py",
        "src/memcommit/adapters/console/commands/forget/command.py",
        "src/memcommit/adapters/console/commands/forget/impact.py",
        "src/memcommit/adapters/console/commands/forget/workbench/screen.py",
        "src/memcommit/application/operations/forget/runtime.py",
    )

    for relative_path in relative_paths:
        path = REPOSITORY_ROOT / relative_path
        source = path.read_text(encoding="utf-8")
        assert "from memcommit.forget_application import" not in source
        assert "from memcommit.forget_runtime import" not in source
