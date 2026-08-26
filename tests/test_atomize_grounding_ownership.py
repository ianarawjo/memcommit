"""Ownership and compatibility paths for the Atomize Grounding slice."""

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
        "memcommit.atomize_grounding_application",
        "memcommit.operations.atomize.grounding_application",
    ),
    (
        "memcommit.atomize_grounding_runtime",
        "memcommit.operations.atomize.grounding_runtime",
    ),
)


@pytest.mark.parametrize("legacy_name,canonical_name", MODULE_PAIRS)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_grounding_module_identity_is_independent_of_import_order(
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


def test_grounding_legacy_paths_expose_the_canonical_contract() -> None:
    legacy_application = importlib.import_module(
        "memcommit.atomize_grounding_application"
    )
    canonical_application = importlib.import_module(
        "memcommit.operations.atomize.grounding_application"
    )
    legacy_runtime = importlib.import_module("memcommit.atomize_grounding_runtime")
    canonical_runtime = importlib.import_module(
        "memcommit.operations.atomize.grounding_runtime"
    )

    assert legacy_application is canonical_application
    assert (
        legacy_application.GroundingStartRequest
        is canonical_application.GroundingStartRequest
    )
    assert (
        legacy_application.run_atomize_grounding_accept
        is canonical_application.run_atomize_grounding_accept
    )
    assert legacy_runtime is canonical_runtime
    assert (
        legacy_runtime.MemoryStoreAtomizeGroundingPort
        is canonical_runtime.MemoryStoreAtomizeGroundingPort
    )
    assert (
        legacy_runtime.assert_current_grounding_bindings
        is canonical_runtime.assert_current_grounding_bindings
    )


@pytest.mark.parametrize(
    "relative_path",
    (
        "src/memcommit/atomize_grounding_application.py",
        "src/memcommit/atomize_grounding_runtime.py",
    ),
)
def test_grounding_legacy_facades_define_no_behavior(relative_path: str) -> None:
    assert_legacy_root_submodule_is_centralized(relative_path)


def test_atomize_package_import_keeps_grounding_lazy() -> None:
    program = """
import sys
import memcommit.operations.atomize

assert "memcommit.operations.atomize.grounding_application" not in sys.modules
assert "memcommit.operations.atomize.grounding_runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_pre_relocation_grounding_request_global_loads_through_alias() -> None:
    canonical = importlib.import_module(
        "memcommit.operations.atomize.grounding_application"
    )

    restored = pickle.loads(
        b"cmemcommit.atomize_grounding_application\nGroundingStartRequest\n."
    )

    assert restored is canonical.GroundingStartRequest


def test_migrated_grounding_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/api/_operations/atomize_grounding.py",
        "src/memcommit/commands/atomize/command.py",
        "src/memcommit/commands/atomize/grounding.py",
        "src/memcommit/operations/atomize/grounding_runtime.py",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "from memcommit.atomize_grounding_application import" not in source
        assert "from memcommit.atomize_grounding_runtime import" not in source


def test_primary_analysis_and_grounding_keep_separate_contracts() -> None:
    grounding = "\n".join(
        (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        for relative_path in (
            "src/memcommit/operations/atomize/grounding_application.py",
            "src/memcommit/operations/atomize/grounding_runtime.py",
        )
    )

    assert "memcommit.operations.atomize.application" not in grounding
    assert "memcommit.operations.atomize.analysis_application" not in grounding
    assert "memcommit.operations.atomize.analysis_runtime" not in grounding
