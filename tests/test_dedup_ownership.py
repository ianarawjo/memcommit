"""Ownership and compatibility paths for reviewed redundancy contracts."""

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
        "memcommit.dedup_application",
        "memcommit.operations.dedup.application",
    ),
    (
        "memcommit.dedup_runtime",
        "memcommit.operations.dedup.runtime",
    ),
)


@pytest.mark.parametrize("legacy_name,canonical_name", MODULE_PAIRS)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_dedup_module_identity_is_independent_of_import_order(
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


def test_dedup_legacy_paths_expose_the_canonical_contract() -> None:
    legacy_application = importlib.import_module("memcommit.dedup_application")
    canonical_application = importlib.import_module(
        "memcommit.operations.dedup.application"
    )
    legacy_runtime = importlib.import_module("memcommit.dedup_runtime")
    canonical_runtime = importlib.import_module(
        "memcommit.operations.dedup.runtime"
    )

    assert legacy_application is canonical_application
    assert legacy_application.DedupRequest is canonical_application.DedupRequest
    assert legacy_application.prepare_dedup is canonical_application.prepare_dedup
    assert legacy_application.apply_dedup is canonical_application.apply_dedup
    assert legacy_runtime is canonical_runtime
    assert (
        legacy_runtime.MemoryStoreDedupPort
        is canonical_runtime.MemoryStoreDedupPort
    )


@pytest.mark.parametrize(
    "relative_path",
    ("memcommit/dedup_application.py", "memcommit/dedup_runtime.py"),
)
def test_dedup_legacy_facades_define_no_behavior(relative_path: str) -> None:
    path = REPOSITORY_ROOT / relative_path
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for node in ast.walk(tree)
    )


def test_dedup_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.operations.dedup

assert "memcommit.operations.dedup.application" not in sys.modules
assert "memcommit.operations.dedup.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_pre_relocation_dedup_request_global_loads_through_alias() -> None:
    canonical = importlib.import_module("memcommit.operations.dedup.application")

    restored = pickle.loads(b"cmemcommit.dedup_application\nDedupRequest\n.")

    assert restored is canonical.DedupRequest


def test_production_dedup_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "memcommit/atomize_normal_form.py",
        "memcommit/api/dedup.py",
        "memcommit/api/_operations/dedup.py",
        "memcommit/commands/consolidate.py",
        "memcommit/commands/duplicate_dedup_handoff.py",
        "memcommit/commands/find_duplicates.py",
        "memcommit/commands/quality_find_workbench.py",
        "memcommit/dedup_planning.py",
        "memcommit/dedun_scope.py",
        "memcommit/interfaces/cli/dedup.py",
        "memcommit/interfaces/tui/operations/dedup/screen.py",
        "memcommit/operations/dedup/runtime.py",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "memcommit.dedup_application" not in source
        assert "memcommit.dedup_runtime" not in source


def test_exact_dedup_and_dedun_scope_remain_separate_owners() -> None:
    application = (
        REPOSITORY_ROOT / "memcommit/operations/dedup/application.py"
    ).read_text(encoding="utf-8")
    runtime = (
        REPOSITORY_ROOT / "memcommit/operations/dedup/runtime.py"
    ).read_text(encoding="utf-8")
    exact = (
        REPOSITORY_ROOT / "memcommit/operations/exact_dedup/application.py"
    ).read_text(encoding="utf-8")
    dedun_scope = (
        REPOSITORY_ROOT / "memcommit/operations/dedun/scope.py"
    ).read_text(encoding="utf-8")

    assert "memcommit.dedun_scope" not in application + runtime
    assert "memcommit.operations.dedup" not in exact
    assert "memcommit.operations.dedup" in dedun_scope
