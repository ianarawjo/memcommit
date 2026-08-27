"""Ownership and compatibility paths for reviewed Meld execution."""

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
        "memcommit.meld_application",
        "memcommit.application.operations.meld.application",
    ),
    (
        "memcommit.meld_runtime",
        "memcommit.application.operations.meld.runtime",
    ),
    (
        "memcommit.meld_application_flow",
        "memcommit.application.operations.meld.application_flow",
    ),
    (
        "memcommit.meld_session_application",
        "memcommit.application.operations.meld.session_application",
    ),
    (
        "memcommit.meld_start_application",
        "memcommit.application.operations.meld.start_application",
    ),
    (
        "memcommit.meld_restart_application",
        "memcommit.application.operations.meld.restart_application",
    ),
    (
        "memcommit.meld_assessment_application",
        "memcommit.application.operations.meld.assessment_application",
    ),
    (
        "memcommit.meld_resolution_application",
        "memcommit.application.operations.meld.resolution_application",
    ),
)

COMPATIBILITY_GLOBALS = (
    (
        "memcommit.meld_application_flow",
        "memcommit.application.operations.meld.application_flow",
        "MeldApplicationFlowPort",
    ),
    (
        "memcommit.meld_session_application",
        "memcommit.application.operations.meld.session_application",
        "MeldSessionSnapshot",
    ),
    (
        "memcommit.meld_start_application",
        "memcommit.application.operations.meld.start_application",
        "MeldStartRequest",
    ),
    (
        "memcommit.meld_restart_application",
        "memcommit.application.operations.meld.restart_application",
        "MeldRestartRequest",
    ),
    (
        "memcommit.meld_assessment_application",
        "memcommit.application.operations.meld.assessment_application",
        "FrozenMeldAssessment",
    ),
    (
        "memcommit.meld_resolution_application",
        "memcommit.application.operations.meld.resolution_application",
        "MeldResolutionTurnRequest",
    ),
)


@pytest.mark.parametrize("legacy_name,canonical_name", MODULE_PAIRS)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_meld_module_identity_is_independent_of_import_order(
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


def test_meld_legacy_paths_expose_the_canonical_contract() -> None:
    legacy_application = importlib.import_module("memcommit.meld_application")
    canonical_application = importlib.import_module(
        "memcommit.application.operations.meld.application"
    )
    legacy_runtime = importlib.import_module("memcommit.meld_runtime")
    canonical_runtime = importlib.import_module("memcommit.application.operations.meld.runtime")

    assert legacy_application is canonical_application
    assert legacy_application.MeldApplyRequest is canonical_application.MeldApplyRequest
    assert legacy_application.run_meld_apply is canonical_application.run_meld_apply
    assert legacy_runtime is canonical_runtime
    assert (
        legacy_runtime.MemoryStoreMeldApplyPort
        is canonical_runtime.MemoryStoreMeldApplyPort
    )
    assert legacy_runtime.execute_meld_apply is canonical_runtime.execute_meld_apply


@pytest.mark.parametrize(
    "relative_path",
    tuple(
        f"{legacy_name.replace('.', '/')}.py"
        for legacy_name, _canonical_name in MODULE_PAIRS
    ),
)
def test_meld_legacy_facades_define_no_behavior(relative_path: str) -> None:
    assert_legacy_root_submodule_is_centralized(relative_path)


def test_meld_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.meld

assert "memcommit.application.operations.meld.application" not in sys.modules
assert "memcommit.application.operations.meld.runtime" not in sys.modules
assert "memcommit.application.operations.meld.application_flow" not in sys.modules
assert "memcommit.application.operations.meld.session_application" not in sys.modules
assert "memcommit.application.operations.meld.start_application" not in sys.modules
assert "memcommit.application.operations.meld.restart_application" not in sys.modules
assert "memcommit.application.operations.meld.assessment_application" not in sys.modules
assert "memcommit.application.operations.meld.resolution_application" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_pre_relocation_meld_globals_load_through_aliases() -> None:
    canonical_application = importlib.import_module(
        "memcommit.application.operations.meld.application"
    )
    canonical_runtime = importlib.import_module("memcommit.application.operations.meld.runtime")

    restored_request = pickle.loads(
        b"cmemcommit.meld_application\nMeldApplyRequest\n."
    )
    restored_runtime_port = pickle.loads(
        b"cmemcommit.meld_runtime\nMemoryStoreMeldApplyPort\n."
    )

    assert restored_request is canonical_application.MeldApplyRequest
    assert restored_runtime_port is canonical_runtime.MemoryStoreMeldApplyPort


@pytest.mark.parametrize(
    "legacy_name,canonical_name,global_name",
    COMPATIBILITY_GLOBALS,
)
def test_pre_relocation_meld_subapplication_globals_load_through_aliases(
    legacy_name: str,
    canonical_name: str,
    global_name: str,
) -> None:
    restored = pickle.loads(
        f"c{legacy_name}\n{global_name}\n.".encode("ascii")
    )
    canonical = importlib.import_module(canonical_name)

    assert restored is getattr(canonical, global_name)


def test_production_meld_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/_operations/meld.py",
        "src/memcommit/commands/meld/command.py",
        "src/memcommit/application/operations/meld/restart_application.py",
        "src/memcommit/application/operations/meld/resolution_application.py",
        "src/memcommit/application/operations/meld/runtime.py",
    )

    legacy_modules = tuple(
        legacy_name for legacy_name, _canonical_name in MODULE_PAIRS
    )

    for relative_path in relative_paths:
        path = REPOSITORY_ROOT / relative_path
        source = path.read_text(encoding="utf-8")
        assert not [name for name in legacy_modules if name in source]
