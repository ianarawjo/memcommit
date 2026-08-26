"""Ownership and compatibility paths for deterministic Resolve."""

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
        "memcommit.resolve_application",
        "memcommit.operations.resolve.application",
    ),
    (
        "memcommit.resolve_runtime",
        "memcommit.operations.resolve.runtime",
    ),
)


@pytest.mark.parametrize("legacy_name,canonical_name", MODULE_PAIRS)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_resolve_module_identity_is_independent_of_import_order(
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


def test_resolve_legacy_paths_expose_the_canonical_contract() -> None:
    legacy_application = importlib.import_module("memcommit.resolve_application")
    canonical_application = importlib.import_module(
        "memcommit.operations.resolve.application"
    )
    legacy_runtime = importlib.import_module("memcommit.resolve_runtime")
    canonical_runtime = importlib.import_module("memcommit.operations.resolve.runtime")

    assert legacy_application is canonical_application
    assert legacy_application.ResolveRequest is canonical_application.ResolveRequest
    assert legacy_application.run_resolve is canonical_application.run_resolve
    assert legacy_application.apply_resolve is canonical_application.apply_resolve
    assert legacy_runtime is canonical_runtime
    assert (
        legacy_runtime.MemoryStoreResolvePort
        is canonical_runtime.MemoryStoreResolvePort
    )


@pytest.mark.parametrize(
    "relative_path",
    ("src/memcommit/resolve_application.py", "src/memcommit/resolve_runtime.py"),
)
def test_resolve_legacy_facades_define_no_behavior(relative_path: str) -> None:
    assert_legacy_root_submodule_is_centralized(relative_path)


def test_resolve_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.operations.resolve

assert "memcommit.operations.resolve.application" not in sys.modules
assert "memcommit.operations.resolve.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_pre_relocation_resolve_globals_load_through_aliases() -> None:
    canonical_application = importlib.import_module(
        "memcommit.operations.resolve.application"
    )
    canonical_runtime = importlib.import_module("memcommit.operations.resolve.runtime")

    restored_request = pickle.loads(
        b"cmemcommit.resolve_application\nResolveRequest\n."
    )
    restored_runtime_port = pickle.loads(
        b"cmemcommit.resolve_runtime\nMemoryStoreResolvePort\n."
    )

    assert restored_request is canonical_application.ResolveRequest
    assert restored_runtime_port is canonical_runtime.MemoryStoreResolvePort


def test_production_resolve_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/api/resolve.py",
        "src/memcommit/api/_operations/resolve.py",
        "src/memcommit/commands/resolve/command.py",
        "src/memcommit/commands/find_conflicts/resolve_handoff.py",
        "src/memcommit/commands/find_conflicts/command.py",
        "src/memcommit/commands/impact/process_local.py",
        "src/memcommit/interfaces/cli/resolve.py",
        "src/memcommit/interfaces/tui/operations/resolve/screen.py",
        "src/memcommit/reviewing/quality/handoff.py",
        "src/memcommit/operations/resolve/semantic.py",
        "src/memcommit/operations/resolve/targeting.py",
        "src/memcommit/operations/resolve/runtime.py",
    )

    for relative_path in relative_paths:
        path = REPOSITORY_ROOT / relative_path
        source = path.read_text(encoding="utf-8")
        assert "from memcommit.resolve_application import" not in source
        assert "from memcommit.resolve_runtime import" not in source
