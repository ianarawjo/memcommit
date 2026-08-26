"""Ownership and compatibility paths for Distill and Elaborate."""

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
    ("memcommit.distill_application", "memcommit.operations.distill.application"),
    ("memcommit.distill_runtime", "memcommit.operations.distill.runtime"),
    ("memcommit.elaborate_application", "memcommit.operations.elaborate.application"),
    ("memcommit.elaborate_runtime", "memcommit.operations.elaborate.runtime"),
    ("memcommit.elaborate_add_runtime", "memcommit.operations.elaborate.add_runtime"),
)


@pytest.mark.parametrize("legacy_name,canonical_name", MODULE_PAIRS)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_module_identity_is_independent_of_import_order(
    legacy_name: str,
    canonical_name: str,
    legacy_first: bool,
) -> None:
    first_name, second_name = (
        (legacy_name, canonical_name) if legacy_first else (canonical_name, legacy_name)
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


@pytest.mark.parametrize(
    "relative_path",
    (
        "src/memcommit/distill_application.py",
        "src/memcommit/distill_runtime.py",
        "src/memcommit/elaborate_application.py",
        "src/memcommit/elaborate_runtime.py",
        "src/memcommit/elaborate_add_runtime.py",
    ),
)
def test_legacy_facades_define_no_behavior(relative_path: str) -> None:
    assert_legacy_root_submodule_is_centralized(relative_path)


@pytest.mark.parametrize("operation", ("distill", "elaborate"))
def test_operation_package_import_is_lazy(operation: str) -> None:
    program = f"""
import sys
import memcommit.operations.{operation}

assert not [
    name
    for name in sys.modules
    if name.startswith("memcommit.operations.{operation}.")
]
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_pre_relocation_globals_load_through_aliases() -> None:
    distill_application = importlib.import_module(
        "memcommit.operations.distill.application"
    )
    distill_runtime = importlib.import_module("memcommit.operations.distill.runtime")
    elaborate_application = importlib.import_module(
        "memcommit.operations.elaborate.application"
    )
    elaborate_add_runtime = importlib.import_module(
        "memcommit.operations.elaborate.add_runtime"
    )

    assert (
        pickle.loads(b"cmemcommit.distill_application\nDistillRequest\n.")
        is distill_application.DistillRequest
    )
    assert (
        pickle.loads(
            b"cmemcommit.distill_runtime\nLocalMemoryStoreDistillSourcePort\n."
        )
        is distill_runtime.LocalMemoryStoreDistillSourcePort
    )
    assert (
        pickle.loads(b"cmemcommit.elaborate_application\nElaborateRequest\n.")
        is elaborate_application.ElaborateRequest
    )
    assert (
        pickle.loads(b"cmemcommit.elaborate_add_runtime\nPreparedElaborateAdd\n.")
        is elaborate_add_runtime.PreparedElaborateAdd
    )


def test_production_consumers_use_operation_owners() -> None:
    relative_paths = (
        "src/memcommit/api/_operations/distill.py",
        "src/memcommit/api/_operations/elaborate.py",
        "src/memcommit/commands/distill/command.py",
        "src/memcommit/commands/elaborate/command.py",
        "src/memcommit/commands/impact/process_local.py",
        "src/memcommit/operations/ground/distill.py",
        "src/memcommit/operations/ground/elaborate.py",
        "src/memcommit/interfaces/cli/distill.py",
        "src/memcommit/interfaces/cli/elaborate.py",
        "src/memcommit/operations/distill/runtime.py",
        "src/memcommit/operations/elaborate/runtime.py",
        "src/memcommit/operations/elaborate/add_runtime.py",
    )
    legacy_imports = (
        "from memcommit.distill_application import",
        "from memcommit.distill_runtime import",
        "from memcommit.elaborate_application import",
        "from memcommit.elaborate_runtime import",
        "from memcommit.elaborate_add_runtime import",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert not [legacy for legacy in legacy_imports if legacy in source]


def test_distill_and_elaborate_keep_distinct_execution_contracts() -> None:
    distill_source = "\n".join(
        (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        for relative_path in (
            "src/memcommit/operations/distill/application.py",
            "src/memcommit/operations/distill/runtime.py",
        )
    )
    elaborate_application = (
        REPOSITORY_ROOT / "src/memcommit/operations/elaborate/application.py"
    ).read_text(encoding="utf-8")
    elaborate_runtime = (
        REPOSITORY_ROOT / "src/memcommit/operations/elaborate/runtime.py"
    ).read_text(encoding="utf-8")
    elaborate_add_runtime = (
        REPOSITORY_ROOT / "src/memcommit/operations/elaborate/add_runtime.py"
    ).read_text(encoding="utf-8")

    assert "memcommit.operations.elaborate" not in distill_source
    assert "memcommit.operations.distill" not in (
        elaborate_application + elaborate_runtime + elaborate_add_runtime
    )
    assert "append_semantic_memories" not in elaborate_runtime
    assert "MemoryStore" not in elaborate_runtime
    assert "from memcommit.operations.elaborate.runtime import" in elaborate_add_runtime
    assert "append_semantic_memories" in elaborate_add_runtime
    assert "prepare_distill_add" in distill_source
    assert "apply_prepared_distill_add" in distill_source


def test_operation_owners_do_not_depend_on_command_or_interface_adapters() -> None:
    package_source = "\n".join(
        path.read_text(encoding="utf-8")
        for package in ("distill", "elaborate")
        for path in sorted(
            (REPOSITORY_ROOT / "src/memcommit/operations" / package).glob("*.py")
        )
    )

    assert "memcommit.commands" not in package_source
    assert "memcommit.interfaces" not in package_source
