"""Ownership and compatibility paths for deterministic Update application."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_NAME = "memcommit.application.operations.update.application"


def test_update_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.update

assert "memcommit.application.operations.update.application" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_update_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/persistence/store/operation_state.py",
        "src/memcommit/persistence/store/context_memory.py",
        "src/memcommit/persistence/store/record_restore_checkpoint.py",
        "src/memcommit/application/operations/update/granted_application.py",
        "src/memcommit/application/operations/update/granted_source_application.py",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "from memcommit.update_application import" not in source


def test_update_does_not_invent_an_operation_runtime() -> None:
    assert not (REPOSITORY_ROOT / "src/memcommit/application/operations/update/runtime.py").exists()
