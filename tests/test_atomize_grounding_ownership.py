"""Ownership and compatibility paths for the Atomize Grounding slice."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_atomize_package_import_keeps_grounding_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.atomize

assert "memcommit.application.operations.atomize.grounding_application" not in sys.modules
assert "memcommit.application.operations.atomize.grounding_runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_migrated_grounding_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/_operations/atomize_grounding.py",
        "src/memcommit/adapters/console/commands/atomize/command.py",
        "src/memcommit/adapters/console/commands/atomize/grounding.py",
        "src/memcommit/application/operations/atomize/grounding_runtime.py",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "from memcommit.atomize_grounding_application import" not in source
        assert "from memcommit.atomize_grounding_runtime import" not in source


def test_primary_analysis_and_grounding_keep_separate_contracts() -> None:
    grounding = "\n".join(
        (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        for relative_path in (
            "src/memcommit/application/operations/atomize/grounding_application.py",
            "src/memcommit/application/operations/atomize/grounding_runtime.py",
        )
    )

    assert "memcommit.application.operations.atomize.application" not in grounding
    assert "memcommit.application.operations.atomize.analysis_application" not in grounding
    assert "memcommit.application.operations.atomize.analysis_runtime" not in grounding
