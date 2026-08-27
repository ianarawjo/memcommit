"""Ownership and compatibility paths for selective Forget."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import pickle
import subprocess
import sys

import pytest

from tests.legacy_submodule_assertions import (
    assert_legacy_root_submodule_is_centralized,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODULE_PAIRS = (
    (
        "memcommit.forget_application",
        "memcommit.application.operations.forget.application",
    ),
    (
        "memcommit.forget_runtime",
        "memcommit.application.operations.forget.runtime",
    ),
)


@pytest.mark.parametrize("legacy_name,canonical_name", MODULE_PAIRS)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_forget_module_identity_is_independent_of_import_order(
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


def test_forget_legacy_paths_expose_the_canonical_contract() -> None:
    legacy_application = importlib.import_module("memcommit.forget_application")
    canonical_application = importlib.import_module(
        "memcommit.application.operations.forget.application"
    )
    legacy_runtime = importlib.import_module("memcommit.forget_runtime")
    canonical_runtime = importlib.import_module("memcommit.application.operations.forget.runtime")

    assert legacy_application is canonical_application
    assert (
        legacy_application.ForgetAnalysisRequest
        is canonical_application.ForgetAnalysisRequest
    )
    assert (
        legacy_application.run_forget_analysis
        is canonical_application.run_forget_analysis
    )
    assert (
        legacy_application.run_forget_apply
        is canonical_application.run_forget_apply
    )
    assert legacy_runtime is canonical_runtime
    assert (
        legacy_runtime.MemoryStoreForgetSourcePort
        is canonical_runtime.MemoryStoreForgetSourcePort
    )
    assert (
        legacy_runtime.execute_forget_analysis
        is canonical_runtime.execute_forget_analysis
    )


@pytest.mark.parametrize(
    "relative_path",
    ("src/memcommit/forget_application.py", "src/memcommit/forget_runtime.py"),
)
def test_forget_legacy_facades_define_no_behavior(relative_path: str) -> None:
    assert_legacy_root_submodule_is_centralized(relative_path)


def test_forget_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.forget

assert "memcommit.application.operations.forget.application" not in sys.modules
assert "memcommit.application.operations.forget.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_pre_relocation_forget_request_global_loads_through_alias() -> None:
    canonical = importlib.import_module("memcommit.application.operations.forget.application")

    restored = pickle.loads(
        b"cmemcommit.forget_application\nForgetAnalysisRequest\n."
    )

    assert restored is canonical.ForgetAnalysisRequest


def test_production_forget_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/forget.py",
        "src/memcommit/adapters/python_api/_operations/forget.py",
        "src/memcommit/commands/forget/command.py",
        "src/memcommit/commands/impact/process_local.py",
        "src/memcommit/adapters/interfaces/tui/operations/forget/workbench.py",
        "src/memcommit/application/operations/forget/runtime.py",
    )

    for relative_path in relative_paths:
        path = REPOSITORY_ROOT / relative_path
        source = path.read_text(encoding="utf-8")
        assert "from memcommit.forget_application import" not in source
        assert "from memcommit.forget_runtime import" not in source
