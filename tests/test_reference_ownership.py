"""Ownership and compatibility paths for immutable Reference."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_reference_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.reference

assert "memcommit.application.operations.reference.application" not in sys.modules
assert "memcommit.application.operations.reference.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_reference_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/_operations/reference.py",
        "src/memcommit/adapters/console/commands/reference/command.py",
        "src/memcommit/adapters/interfaces/tui/operations/reference/adapter.py",
        "src/memcommit/adapters/interfaces/tui/operations/reference/screen.py",
        "src/memcommit/application/operations/reference/runtime.py",
    )

    for relative_path in relative_paths:
        path = REPOSITORY_ROOT / relative_path
        source = path.read_text(encoding="utf-8")
        assert "from memcommit.reference_application import" not in source
        assert "from memcommit.reference_runtime import" not in source


def test_reference_cli_has_one_command_owned_implementation() -> None:
    assert not (
        REPOSITORY_ROOT / "src/memcommit/adapters/interfaces/cli/reference.py"
    ).exists()


def test_query_reference_remains_owned_by_the_query_operation() -> None:
    application = (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/query/reference_application.py"
    ).read_text(encoding="utf-8")
    runtime = (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/query/reference_runtime.py"
    ).read_text(encoding="utf-8")

    assert "memcommit.application.operations.reference" not in application
    assert "memcommit.application.operations.reference" not in runtime
