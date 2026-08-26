"""Ownership and compatibility paths for primary structural Atomize."""

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
        "memcommit.atomize_application",
        "memcommit.operations.atomize.application",
    ),
    (
        "memcommit.atomize_runtime",
        "memcommit.operations.atomize.runtime",
    ),
)


@pytest.mark.parametrize("legacy_name,canonical_name", MODULE_PAIRS)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_atomize_module_identity_is_independent_of_import_order(
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


def test_atomize_legacy_paths_expose_the_canonical_contract() -> None:
    legacy_application = importlib.import_module("memcommit.atomize_application")
    canonical_application = importlib.import_module(
        "memcommit.operations.atomize.application"
    )
    legacy_runtime = importlib.import_module("memcommit.atomize_runtime")
    canonical_runtime = importlib.import_module(
        "memcommit.operations.atomize.runtime"
    )

    assert legacy_application is canonical_application
    assert (
        legacy_application.AtomizeSessionSnapshot
        is canonical_application.AtomizeSessionSnapshot
    )
    assert (
        legacy_application.run_atomize_session_apply
        is canonical_application.run_atomize_session_apply
    )
    assert legacy_runtime is canonical_runtime
    assert (
        legacy_runtime.MemoryStoreAtomizeSessionRepository
        is canonical_runtime.MemoryStoreAtomizeSessionRepository
    )
    assert (
        legacy_runtime.execute_atomize_session_apply
        is canonical_runtime.execute_atomize_session_apply
    )


@pytest.mark.parametrize(
    "relative_path",
    ("src/memcommit/atomize_application.py", "src/memcommit/atomize_runtime.py"),
)
def test_atomize_legacy_facades_define_no_behavior(relative_path: str) -> None:
    assert_legacy_root_submodule_is_centralized(relative_path)


def test_atomize_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.operations.atomize

assert "memcommit.operations.atomize.application" not in sys.modules
assert "memcommit.operations.atomize.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_pre_relocation_atomize_snapshot_global_loads_through_alias() -> None:
    canonical = importlib.import_module("memcommit.operations.atomize.application")

    restored = pickle.loads(
        b"cmemcommit.atomize_application\nAtomizeSessionSnapshot\n."
    )

    assert restored is canonical.AtomizeSessionSnapshot


def test_primary_atomize_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/api/atomize.py",
        "src/memcommit/api/_operations/atomize.py",
        "src/memcommit/commands/atomize/command.py",
        "src/memcommit/operations/atomize/runtime.py",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "memcommit.atomize_application" not in source
        assert "memcommit.atomize_runtime" not in source


def test_analysis_and_grounding_remain_separate_atomize_slices() -> None:
    primary = "\n".join(
        (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        for relative_path in (
            "src/memcommit/operations/atomize/application.py",
            "src/memcommit/operations/atomize/runtime.py",
        )
    )
    analysis_application = (
        REPOSITORY_ROOT
        / "src/memcommit/operations/atomize/analysis_application.py"
    ).read_text(encoding="utf-8")
    grounding_application = (
        REPOSITORY_ROOT
        / "src/memcommit/operations/atomize/grounding_application.py"
    ).read_text(encoding="utf-8")

    assert "memcommit.atomize_analysis_application" not in primary
    assert "memcommit.atomize_grounding_application" not in primary
    assert "class AtomizeAnalysisOpenRequest" in analysis_application
    assert "class GroundingAcceptRequest" in grounding_application
