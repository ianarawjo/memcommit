"""Ownership and compatibility paths for read-only Show."""

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
    ("memcommit.show_application", "memcommit.application.operations.show.application"),
    ("memcommit.show_runtime", "memcommit.application.operations.show.runtime"),
)


@pytest.mark.parametrize("legacy_name,canonical_name", MODULE_PAIRS)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_show_module_identity_is_independent_of_import_order(
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


def test_show_legacy_paths_expose_the_canonical_contract() -> None:
    legacy_application = importlib.import_module("memcommit.show_application")
    canonical_application = importlib.import_module(
        "memcommit.application.operations.show.application"
    )
    legacy_runtime = importlib.import_module("memcommit.show_runtime")
    canonical_runtime = importlib.import_module("memcommit.application.operations.show.runtime")

    assert legacy_application is canonical_application
    assert legacy_application.ShowRequest is canonical_application.ShowRequest
    assert legacy_application.show is canonical_application.show
    assert legacy_runtime is canonical_runtime
    assert legacy_runtime.MemoryStoreShowPort is canonical_runtime.MemoryStoreShowPort
    assert legacy_runtime.execute_show is canonical_runtime.execute_show


@pytest.mark.parametrize(
    "relative_path",
    ("src/memcommit/show_application.py", "src/memcommit/show_runtime.py"),
)
def test_show_legacy_facades_define_no_behavior(relative_path: str) -> None:
    assert_legacy_root_submodule_is_centralized(relative_path)


def test_show_operation_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.show

assert "memcommit.application.operations.show.application" not in sys.modules
assert "memcommit.application.operations.show.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_pre_relocation_show_globals_load_through_aliases() -> None:
    canonical_application = importlib.import_module(
        "memcommit.application.operations.show.application"
    )
    canonical_runtime = importlib.import_module("memcommit.application.operations.show.runtime")

    restored_request = pickle.loads(
        b"cmemcommit.show_application\nShowRequest\n."
    )
    restored_port = pickle.loads(
        b"cmemcommit.show_runtime\nMemoryStoreShowPort\n."
    )

    assert restored_request is canonical_application.ShowRequest
    assert restored_port is canonical_runtime.MemoryStoreShowPort


def test_production_show_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/_operations/show.py",
        "src/memcommit/commands/show/command.py",
        "src/memcommit/interfaces/cli/show.py",
        "src/memcommit/application/operations/show/runtime.py",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "from memcommit.show_application import" not in source
        assert "from memcommit.show_runtime import" not in source


def test_show_owner_retains_read_only_effect_boundary() -> None:
    application_source = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/show/application.py"
    ).read_text(encoding="utf-8")
    runtime_source = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/show/runtime.py"
    ).read_text(encoding="utf-8")
    combined = application_source + runtime_source

    assert "memcommit.commands" not in combined
    assert "memcommit.interfaces" not in combined
    assert "provider.complete" not in combined
    assert "store.save(" not in runtime_source
    assert "set_current(" not in runtime_source
