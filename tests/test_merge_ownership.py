"""Ownership and compatibility paths for the Merge operation slice."""

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
        "memcommit.merge_application",
        "memcommit.operations.merge.application",
    ),
    (
        "memcommit.merge_runtime",
        "memcommit.operations.merge.runtime",
    ),
)


@pytest.mark.parametrize("legacy_name,canonical_name", MODULE_PAIRS)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_merge_module_identity_is_independent_of_import_order(
    legacy_name: str,
    canonical_name: str,
    legacy_first: bool,
) -> None:
    first_name, second_name = (
        (legacy_name, canonical_name) if legacy_first else (canonical_name, legacy_name)
    )
    source = f"""
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
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_merge_legacy_paths_expose_canonical_objects() -> None:
    legacy_application = importlib.import_module("memcommit.merge_application")
    canonical_application = importlib.import_module(
        "memcommit.operations.merge.application"
    )
    legacy_runtime = importlib.import_module("memcommit.merge_runtime")
    canonical_runtime = importlib.import_module("memcommit.operations.merge.runtime")

    assert legacy_application is canonical_application
    assert legacy_application.MergeRequest is canonical_application.MergeRequest
    assert legacy_application.prepare_merge is canonical_application.prepare_merge
    assert legacy_application.run_merge is canonical_application.run_merge
    assert legacy_runtime is canonical_runtime
    assert legacy_runtime.MemoryStoreMergePort is canonical_runtime.MemoryStoreMergePort
    assert legacy_runtime.execute_merge is canonical_runtime.execute_merge


@pytest.mark.parametrize(
    "relative_path",
    ("memcommit/merge_application.py", "memcommit/merge_runtime.py"),
)
def test_merge_legacy_facades_define_no_behavior(relative_path: str) -> None:
    path = REPOSITORY_ROOT / relative_path
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for node in ast.walk(tree)
    )


def test_merge_package_import_is_lazy() -> None:
    source = """
import sys
import memcommit.operations.merge

assert "memcommit.operations.merge.application" not in sys.modules
assert "memcommit.operations.merge.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_pre_relocation_merge_global_loads_through_legacy_alias() -> None:
    canonical = importlib.import_module("memcommit.operations.merge.application")

    restored = pickle.loads(b"cmemcommit.merge_application\nMergeRequest\n.")

    assert restored is canonical.MergeRequest
