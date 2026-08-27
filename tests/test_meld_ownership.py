"""Ownership and compatibility paths for reviewed Meld execution."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODULE_PAIRS = (
    (
        "memcommit.meld_application",
        "memcommit.application.operations.meld.application",
    ),
    (
        "memcommit.meld_runtime",
        "memcommit.application.operations.meld.runtime",
    ),
    (
        "memcommit.meld_application_flow",
        "memcommit.application.operations.meld.application_flow",
    ),
    (
        "memcommit.meld_session_application",
        "memcommit.application.operations.meld.session_application",
    ),
    (
        "memcommit.meld_start_application",
        "memcommit.application.operations.meld.start_application",
    ),
    (
        "memcommit.meld_restart_application",
        "memcommit.application.operations.meld.restart_application",
    ),
    (
        "memcommit.meld_assessment_application",
        "memcommit.application.operations.meld.assessment_application",
    ),
    (
        "memcommit.meld_resolution_application",
        "memcommit.application.operations.meld.resolution_application",
    ),
)


def test_meld_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.meld

assert "memcommit.application.operations.meld.application" not in sys.modules
assert "memcommit.application.operations.meld.runtime" not in sys.modules
assert "memcommit.application.operations.meld.application_flow" not in sys.modules
assert "memcommit.application.operations.meld.session_application" not in sys.modules
assert "memcommit.application.operations.meld.start_application" not in sys.modules
assert "memcommit.application.operations.meld.restart_application" not in sys.modules
assert "memcommit.application.operations.meld.assessment_application" not in sys.modules
assert "memcommit.application.operations.meld.resolution_application" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_meld_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/_operations/meld.py",
        "src/memcommit/commands/meld/command.py",
        "src/memcommit/application/operations/meld/restart_application.py",
        "src/memcommit/application/operations/meld/resolution_application.py",
        "src/memcommit/application/operations/meld/runtime.py",
    )

    legacy_modules = tuple(
        legacy_name for legacy_name, _canonical_name in MODULE_PAIRS
    )

    for relative_path in relative_paths:
        path = REPOSITORY_ROOT / relative_path
        source = path.read_text(encoding="utf-8")
        assert not [name for name in legacy_modules if name in source]
