"""Ownership and compatibility paths for the Edit operation slice."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import subprocess
import sys

import pytest

from tests.legacy_submodule_assertions import (
    assert_legacy_root_submodule_is_centralized,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LEGACY_AND_CANONICAL_PATHS = (
    (
        "memcommit.edit_application",
        "memcommit.application.operations.edit.application",
    ),
    (
        "memcommit.edit_runtime",
        "memcommit.application.operations.edit.runtime",
    ),
)


@pytest.mark.parametrize(
    "legacy_name,canonical_name",
    LEGACY_AND_CANONICAL_PATHS,
)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_edit_module_identity_is_independent_of_import_order(
    legacy_name: str,
    canonical_name: str,
    legacy_first: bool,
) -> None:
    first_name, second_name = (
        (legacy_name, canonical_name)
        if legacy_first
        else (canonical_name, legacy_name)
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


def test_edit_legacy_paths_expose_the_canonical_objects() -> None:
    legacy_application = importlib.import_module("memcommit.edit_application")
    canonical_application = importlib.import_module(
        "memcommit.application.operations.edit.application"
    )
    legacy_runtime = importlib.import_module("memcommit.edit_runtime")
    canonical_runtime = importlib.import_module("memcommit.application.operations.edit.runtime")

    assert legacy_application is canonical_application
    assert legacy_application.EditRequest is canonical_application.EditRequest
    assert legacy_application.run_edit is canonical_application.run_edit
    assert legacy_runtime is canonical_runtime
    assert legacy_runtime.MemoryStoreEditPort is canonical_runtime.MemoryStoreEditPort
    assert legacy_runtime.execute_edit is canonical_runtime.execute_edit


@pytest.mark.parametrize(
    "relative_path",
    (
        "src/memcommit/edit_application.py",
        "src/memcommit/edit_runtime.py",
    ),
)
def test_edit_legacy_facades_contain_no_implementation(relative_path: str) -> None:
    assert_legacy_root_submodule_is_centralized(relative_path)
