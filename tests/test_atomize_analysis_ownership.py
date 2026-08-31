"""Ownership and compatibility paths for the Atomize Analysis slice."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_existing_atomize_package_keeps_analysis_import_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.atomize

assert "memcommit.application.operations.atomize.analysis_application" not in sys.modules
assert "memcommit.application.operations.atomize.analysis_runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_migrated_atomize_analysis_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/_operations/atomize.py",
        "src/memcommit/adapters/console/commands/atomize/command.py",
        "src/memcommit/adapters/console/commands/atomize/impact.py",
        "src/memcommit/adapters/console/commands/impact/command.py",
        "src/memcommit/application/operations/atomize/analysis_runtime.py",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "memcommit.atomize_analysis_application" not in source
        assert "memcommit.atomize_analysis_runtime" not in source


def test_analysis_does_not_absorb_grounding_application_or_runtime() -> None:
    analysis = "\n".join(
        (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        for relative_path in (
            "src/memcommit/application/operations/atomize/analysis_application.py",
            "src/memcommit/application/operations/atomize/analysis_runtime.py",
        )
    )

    assert "memcommit.atomize_grounding_application" not in analysis
    assert "memcommit.atomize_grounding_runtime" not in analysis
