"""Ownership and compatibility paths for primary structural Atomize."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_atomize_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.atomize

assert "memcommit.application.operations.atomize.application" not in sys.modules
assert "memcommit.application.operations.atomize.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_primary_atomize_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/atomize.py",
        "src/memcommit/adapters/python_api/_operations/atomize.py",
        "src/memcommit/commands/atomize/command.py",
        "src/memcommit/application/operations/atomize/runtime.py",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "memcommit.atomize_application" not in source
        assert "memcommit.atomize_runtime" not in source


def test_analysis_and_grounding_remain_separate_atomize_slices() -> None:
    primary = "\n".join(
        (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        for relative_path in (
            "src/memcommit/application/operations/atomize/application.py",
            "src/memcommit/application/operations/atomize/runtime.py",
        )
    )
    analysis_application = (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/atomize/analysis_application.py"
    ).read_text(encoding="utf-8")
    grounding_application = (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/atomize/grounding_application.py"
    ).read_text(encoding="utf-8")

    assert "memcommit.atomize_analysis_application" not in primary
    assert "memcommit.atomize_grounding_application" not in primary
    assert "class AtomizeAnalysisOpenRequest" in analysis_application
    assert "class GroundingAcceptRequest" in grounding_application
