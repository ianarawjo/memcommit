"""Ownership and compatibility paths for the Atomize Analysis slice."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import pickle
import subprocess
import sys

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODULE_PAIRS = (
    (
        "memcommit.atomize_analysis_application",
        "memcommit.operations.atomize.analysis_application",
    ),
    (
        "memcommit.atomize_analysis_runtime",
        "memcommit.operations.atomize.analysis_runtime",
    ),
)


@pytest.mark.parametrize("legacy_name,canonical_name", MODULE_PAIRS)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_atomize_analysis_module_identity_is_independent_of_import_order(
    legacy_name: str,
    canonical_name: str,
    legacy_first: bool,
) -> None:
    first_name, second_name = (
        (legacy_name, canonical_name)
        if legacy_first
        else (canonical_name, legacy_name)
    )
    program = f"""
import importlib
import sys

first = importlib.import_module({first_name!r})
second = importlib.import_module({second_name!r})
legacy = importlib.import_module({legacy_name!r})
canonical = importlib.import_module({canonical_name!r})

assert first is second
assert legacy is canonical
assert sys.modules[{legacy_name!r}] is canonical
assert sys.modules[{canonical_name!r}] is canonical
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_atomize_analysis_legacy_paths_expose_the_canonical_contract() -> None:
    legacy_application = importlib.import_module(
        "memcommit.atomize_analysis_application"
    )
    canonical_application = importlib.import_module(
        "memcommit.operations.atomize.analysis_application"
    )
    legacy_runtime = importlib.import_module("memcommit.atomize_analysis_runtime")
    canonical_runtime = importlib.import_module(
        "memcommit.operations.atomize.analysis_runtime"
    )

    assert legacy_application is canonical_application
    assert (
        legacy_application.AtomizeAnalysisOpenRequest
        is canonical_application.AtomizeAnalysisOpenRequest
    )
    assert (
        legacy_application.run_atomize_analysis_open
        is canonical_application.run_atomize_analysis_open
    )
    assert legacy_runtime is canonical_runtime
    assert (
        legacy_runtime.MemoryStoreAtomizeAnalysisOpenPort
        is canonical_runtime.MemoryStoreAtomizeAnalysisOpenPort
    )
    assert (
        legacy_runtime.execute_atomize_analysis_open
        is canonical_runtime.execute_atomize_analysis_open
    )


@pytest.mark.parametrize(
    "relative_path",
    (
        "memcommit/atomize_analysis_application.py",
        "memcommit/atomize_analysis_runtime.py",
    ),
)
def test_atomize_analysis_legacy_facades_define_no_behavior(
    relative_path: str,
) -> None:
    path = REPOSITORY_ROOT / relative_path
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for node in ast.walk(tree)
    )


def test_existing_atomize_package_keeps_analysis_import_lazy() -> None:
    program = """
import sys
import memcommit.operations.atomize

assert "memcommit.operations.atomize.analysis_application" not in sys.modules
assert "memcommit.operations.atomize.analysis_runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_pre_relocation_atomize_analysis_request_loads_through_alias() -> None:
    canonical = importlib.import_module(
        "memcommit.operations.atomize.analysis_application"
    )

    restored = pickle.loads(
        b"cmemcommit.atomize_analysis_application\nAtomizeAnalysisOpenRequest\n."
    )

    assert restored is canonical.AtomizeAnalysisOpenRequest


def test_migrated_atomize_analysis_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "memcommit/atomize_workflow.py",
        "memcommit/api/_operations/atomize.py",
        "memcommit/commands/atomize.py",
        "memcommit/commands/impact.py",
        "memcommit/operations/atomize/analysis_runtime.py",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "memcommit.atomize_analysis_application" not in source
        assert "memcommit.atomize_analysis_runtime" not in source


def test_analysis_does_not_absorb_grounding_application_or_runtime() -> None:
    analysis = "\n".join(
        (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        for relative_path in (
            "memcommit/operations/atomize/analysis_application.py",
            "memcommit/operations/atomize/analysis_runtime.py",
        )
    )

    assert "memcommit.atomize_grounding_application" not in analysis
    assert "memcommit.atomize_grounding_runtime" not in analysis
