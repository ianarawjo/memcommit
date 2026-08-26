"""Ownership and compatibility paths for deterministic Replace."""

from __future__ import annotations

import ast
import base64
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
LEGACY_AND_CANONICAL_PATHS = (
    (
        "memcommit.replace_application",
        "memcommit.operations.replace.application",
    ),
    (
        "memcommit.replace_runtime",
        "memcommit.operations.replace.runtime",
    ),
)

# This protocol-4 payload was created before the ownership relocation. Its
# GLOBAL opcode names memcommit.replace_application.ReplaceRequest directly.
_LEGACY_REPLACE_REQUEST_PICKLE = (
    "gASVZQAAAAAAAACMHW1lbWNvbW1pdC5yZXBsYWNlX2FwcGxpY2F0aW9ulIwO"
    "UmVwbGFjZVJlcXVlc3SUk5QpgZRdlCiMBm5lZWRsZZSMBnRocmVhZJSMBWFs"
    "cGhhlIWUiYmMB0xJVEVSQUyUiWViLg=="
)


@pytest.mark.parametrize(
    "legacy_name,canonical_name",
    LEGACY_AND_CANONICAL_PATHS,
)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_replace_module_identity_is_independent_of_import_order(
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


def test_replace_legacy_paths_expose_the_canonical_objects() -> None:
    legacy_application = importlib.import_module("memcommit.replace_application")
    canonical_application = importlib.import_module(
        "memcommit.operations.replace.application"
    )
    legacy_runtime = importlib.import_module("memcommit.replace_runtime")
    canonical_runtime = importlib.import_module(
        "memcommit.operations.replace.runtime"
    )

    assert legacy_application is canonical_application
    assert legacy_application.ReplaceRequest is canonical_application.ReplaceRequest
    assert legacy_application.FrozenReplacePlan is canonical_application.FrozenReplacePlan
    assert legacy_application.plan_replace is canonical_application.plan_replace
    assert legacy_runtime is canonical_runtime
    assert legacy_runtime.MemoryStoreReplacePort is canonical_runtime.MemoryStoreReplacePort
    assert legacy_runtime.execute_replace_plan is canonical_runtime.execute_replace_plan


@pytest.mark.parametrize(
    "relative_path",
    (
        "memcommit/replace_application.py",
        "memcommit/replace_runtime.py",
    ),
)
def test_replace_legacy_facades_contain_no_implementation(
    relative_path: str,
) -> None:
    assert_legacy_root_submodule_is_centralized(relative_path)


def test_replace_package_import_does_not_eagerly_load_implementation_modules() -> None:
    source = """
import sys
import memcommit.operations.replace

assert "memcommit.operations.replace.application" not in sys.modules
assert "memcommit.operations.replace.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_pre_relocation_replace_request_pickle_loads_through_legacy_alias() -> None:
    canonical = importlib.import_module("memcommit.operations.replace.application")

    restored = pickle.loads(base64.b64decode(_LEGACY_REPLACE_REQUEST_PICKLE))

    assert restored.__class__ is canonical.ReplaceRequest
    assert restored == canonical.ReplaceRequest("needle", "thread", ("alpha",))
    assert restored.__class__.__module__ == "memcommit.operations.replace.application"
