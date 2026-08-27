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
        "src/memcommit/adapters/console/commands/find_conflicts/resolve_handoff.py",
        "src/memcommit/adapters/console/commands/find_conflicts/command.py",
        "src/memcommit/adapters/console/commands/impact/process_local.py",
        "src/memcommit/adapters/interfaces/cli/resolve.py",
        "src/memcommit/adapters/interfaces/tui/operations/resolve/screen.py",
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
