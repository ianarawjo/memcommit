"""Ownership and compatibility paths for immutable Reference."""

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
        "memcommit.reference_application",
        "memcommit.operations.reference.application",
    ),
    (
        "memcommit.reference_runtime",
        "memcommit.operations.reference.runtime",
    ),
)


@pytest.mark.parametrize("legacy_name,canonical_name", MODULE_PAIRS)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_reference_module_identity_is_independent_of_import_order(
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


def test_reference_legacy_paths_expose_the_canonical_contract() -> None:
    legacy_application = importlib.import_module("memcommit.reference_application")
    canonical_application = importlib.import_module(
        "memcommit.operations.reference.application"
    )
    legacy_runtime = importlib.import_module("memcommit.reference_runtime")
    canonical_runtime = importlib.import_module(
        "memcommit.operations.reference.runtime"
    )

    assert legacy_application is canonical_application
    assert legacy_application.ReferenceRequest is canonical_application.ReferenceRequest
    assert (
        legacy_application.ContextReferenceRequest
        is canonical_application.ContextReferenceRequest
    )
    assert legacy_application.run_reference is canonical_application.run_reference
    assert legacy_runtime is canonical_runtime
    assert (
        legacy_runtime.MemoryStoreReferencePort
        is canonical_runtime.MemoryStoreReferencePort
    )
    assert legacy_runtime.execute_reference is canonical_runtime.execute_reference


@pytest.mark.parametrize(
    "relative_path",
    ("memcommit/reference_application.py", "memcommit/reference_runtime.py"),
)
def test_reference_legacy_facades_define_no_behavior(relative_path: str) -> None:
    path = REPOSITORY_ROOT / relative_path
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for node in ast.walk(tree)
    )


def test_reference_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.operations.reference

assert "memcommit.operations.reference.application" not in sys.modules
assert "memcommit.operations.reference.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_pre_relocation_reference_request_global_loads_through_alias() -> None:
    canonical = importlib.import_module(
        "memcommit.operations.reference.application"
    )

    restored = pickle.loads(
        b"cmemcommit.reference_application\nReferenceRequest\n."
    )

    assert restored is canonical.ReferenceRequest


def test_production_reference_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "memcommit/api/_operations/reference.py",
        "memcommit/interfaces/cli/reference.py",
        "memcommit/interfaces/tui/operations/reference/adapter.py",
        "memcommit/interfaces/tui/operations/reference/screen.py",
        "memcommit/operations/reference/runtime.py",
    )

    for relative_path in relative_paths:
        path = REPOSITORY_ROOT / relative_path
        source = path.read_text(encoding="utf-8")
        assert "from memcommit.reference_application import" not in source
        assert "from memcommit.reference_runtime import" not in source


def test_query_reference_remains_owned_by_the_query_operation() -> None:
    application = (
        REPOSITORY_ROOT
        / "memcommit/operations/query/reference_application.py"
    ).read_text(encoding="utf-8")
    runtime = (
        REPOSITORY_ROOT
        / "memcommit/operations/query/reference_runtime.py"
    ).read_text(encoding="utf-8")

    assert "memcommit.operations.reference" not in application
    assert "memcommit.operations.reference" not in runtime
