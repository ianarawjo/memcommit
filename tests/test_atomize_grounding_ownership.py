"""Compatibility ownership for retired Atomize Grounding records."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_atomize_grounding_has_no_executable_route() -> None:
    retired_paths = (
        "src/memcommit/adapters/agent/atomize_grounding.py",
        "src/memcommit/adapters/console/commands/atomize/grounding.py",
        "src/memcommit/adapters/python_api/atomize_grounding.py",
        "src/memcommit/adapters/python_api/_operations/atomize_grounding.py",
        "src/memcommit/application/operations/atomize/grounding_application.py",
        "src/memcommit/application/operations/atomize/grounding_provider.py",
        "src/memcommit/application/operations/atomize/grounding_runtime.py",
    )

    assert all(not (REPOSITORY_ROOT / path).exists() for path in retired_paths)


def test_atomize_package_import_keeps_legacy_grounding_records_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.atomize

assert "memcommit.application.operations.atomize.grounding" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_legacy_grounding_records_preserve_concept_owned_model_modules() -> None:
    from memcommit.application.operations.atomize.grounding import (
        AtomizeGroundingAssessment,
        AtomizeGroundingBindings,
        AtomizeGroundingChangeSet,
        AtomizeGroundingSession,
    )

    assert AtomizeGroundingBindings.__module__.endswith(".grounding.bindings")
    assert AtomizeGroundingAssessment.__module__.endswith(".grounding.review")
    assert AtomizeGroundingChangeSet.__module__.endswith(".grounding.changes")
    assert AtomizeGroundingSession.__module__.endswith(".grounding.session")
