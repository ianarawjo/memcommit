"""Compatibility evidence for the Status ownership-only relocation."""

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


REPOSITORY_ROOT = Path(__file__).parents[1]
STATUS_MODULES = (
    ("memcommit.status_application", "memcommit.application.operations.status.application"),
    ("memcommit.status_runtime", "memcommit.application.operations.status.runtime"),
)


def test_legacy_status_application_path_is_the_canonical_module() -> None:
    legacy = importlib.import_module("memcommit.status_application")
    canonical = importlib.import_module("memcommit.application.operations.status.application")

    assert legacy is canonical
    assert legacy.StatusRequest is canonical.StatusRequest
    assert legacy.inspect_status is canonical.inspect_status


def test_legacy_status_runtime_path_is_the_canonical_module() -> None:
    legacy = importlib.import_module("memcommit.status_runtime")
    canonical = importlib.import_module("memcommit.application.operations.status.runtime")

    assert legacy is canonical
    assert legacy.MemoryStoreStatusSource is canonical.MemoryStoreStatusSource
    assert legacy.execute_status is canonical.execute_status


@pytest.mark.parametrize("legacy_name,canonical_name", STATUS_MODULES)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_status_module_identity_is_independent_of_import_order(
    legacy_name: str,
    canonical_name: str,
    legacy_first: bool,
) -> None:
    first_name, second_name = (
        (legacy_name, canonical_name)
        if legacy_first
        else (canonical_name, legacy_name)
    )
    program = (
        "import importlib\n"
        f"first = importlib.import_module({first_name!r})\n"
        f"second = importlib.import_module({second_name!r})\n"
        "assert first is second\n"
    )

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


@pytest.mark.parametrize(
    "relative_path",
    ("src/memcommit/status_application.py", "src/memcommit/status_runtime.py"),
)
def test_legacy_status_facades_define_no_behavior(relative_path: str) -> None:
    assert_legacy_root_submodule_is_centralized(relative_path)
