"""Ownership and compatibility paths for deterministic Update application."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import pickle
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LEGACY_NAME = "memcommit.update_application"
CANONICAL_NAME = "memcommit.operations.update.application"


def test_update_module_identity_when_legacy_path_is_imported_first() -> None:
    _assert_import_order(LEGACY_NAME, CANONICAL_NAME)


def test_update_module_identity_when_canonical_path_is_imported_first() -> None:
    _assert_import_order(CANONICAL_NAME, LEGACY_NAME)


def _assert_import_order(first_name: str, second_name: str) -> None:
    program = f"""
import importlib
import sys

first = importlib.import_module({first_name!r})
second = importlib.import_module({second_name!r})
legacy = importlib.import_module({LEGACY_NAME!r})
canonical = importlib.import_module({CANONICAL_NAME!r})

assert first is second
assert legacy is canonical
assert sys.modules[{LEGACY_NAME!r}] is canonical
assert sys.modules[{CANONICAL_NAME!r}] is canonical
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_update_legacy_path_exposes_the_canonical_contract() -> None:
    legacy = importlib.import_module(LEGACY_NAME)
    canonical = importlib.import_module(CANONICAL_NAME)

    assert legacy is canonical
    assert legacy.AppliedOwner is canonical.AppliedOwner
    assert legacy.UpdateApplicationResult is canonical.UpdateApplicationResult
    assert (
        legacy.prepare_update_application
        is canonical.prepare_update_application
    )


def test_update_legacy_facade_defines_no_behavior() -> None:
    path = REPOSITORY_ROOT / "memcommit/update_application.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for node in ast.walk(tree)
    )


def test_update_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.operations.update

assert "memcommit.operations.update.application" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_pre_relocation_update_result_global_loads_through_alias() -> None:
    canonical = importlib.import_module(CANONICAL_NAME)

    restored = pickle.loads(
        b"cmemcommit.update_application\nUpdateApplicationResult\n."
    )

    assert restored is canonical.UpdateApplicationResult


def test_production_update_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "memcommit/store.py",
        "memcommit/granted_update_application.py",
        "memcommit/granted_source_update_application.py",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "from memcommit.update_application import" not in source


def test_update_does_not_invent_an_operation_runtime() -> None:
    assert not (REPOSITORY_ROOT / "memcommit/operations/update/runtime.py").exists()
