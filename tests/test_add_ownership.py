"""Ownership and compatibility paths for exact user-supplied Add."""

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
        "memcommit.add_application",
        "memcommit.application.operations.add.application",
    ),
    (
        "memcommit.add_runtime",
        "memcommit.application.operations.add.runtime",
    ),
)


@pytest.mark.parametrize("legacy_name,canonical_name", MODULE_PAIRS)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_add_module_identity_is_independent_of_import_order(
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


def test_add_legacy_paths_expose_the_canonical_contract() -> None:
    legacy_application = importlib.import_module("memcommit.add_application")
    canonical_application = importlib.import_module(
        "memcommit.application.operations.add.application"
    )
    legacy_runtime = importlib.import_module("memcommit.add_runtime")
    canonical_runtime = importlib.import_module("memcommit.application.operations.add.runtime")

    assert legacy_application is canonical_application
    assert legacy_application.AddRequest is canonical_application.AddRequest
    assert legacy_application.run_add is canonical_application.run_add
    assert legacy_runtime is canonical_runtime
    assert (
        legacy_runtime.MemoryStoreAddTargetPort
        is canonical_runtime.MemoryStoreAddTargetPort
    )
    assert legacy_runtime.execute_add is canonical_runtime.execute_add


@pytest.mark.parametrize(
    "relative_path",
    ("src/memcommit/add_application.py", "src/memcommit/add_runtime.py"),
)
def test_add_legacy_facades_define_no_behavior(relative_path: str) -> None:
    assert_legacy_root_submodule_is_centralized(relative_path)


def test_add_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.add

assert "memcommit.application.operations.add.application" not in sys.modules
assert "memcommit.application.operations.add.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_pre_relocation_add_request_global_loads_through_alias() -> None:
    canonical = importlib.import_module("memcommit.application.operations.add.application")

    restored = pickle.loads(b"cmemcommit.add_application\nAddRequest\n.")

    assert restored is canonical.AddRequest


def test_production_add_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/_operations/add.py",
        "src/memcommit/commands/add/command.py",
        "src/memcommit/adapters/interfaces/cli/add.py",
        "src/memcommit/adapters/interfaces/tui/operations/add/screen.py",
        "src/memcommit/application/operations/add/runtime.py",
    )

    for relative_path in relative_paths:
        path = REPOSITORY_ROOT / relative_path
        source = path.read_text(encoding="utf-8")
        assert "from memcommit.add_application import" not in source
        assert "from memcommit.add_runtime import" not in source


def test_exact_add_does_not_absorb_semantic_materialization_helpers() -> None:
    for relative_path in (
        "src/memcommit/application/operations/add/application.py",
        "src/memcommit/application/operations/add/runtime.py",
    ):
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "memcommit.semantic_add_runtime" not in source
        assert "memcommit.elaborate_add_runtime" not in source
        assert "memcommit.application.operations.elaborate.add_runtime" not in source
