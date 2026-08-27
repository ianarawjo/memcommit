"""Ownership and compatibility paths for the unified Delete operation."""

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
        "memcommit.delete_application",
        "memcommit.application.operations.delete.application",
    ),
    (
        "memcommit.delete_runtime",
        "memcommit.application.operations.delete.runtime",
    ),
)

# This protocol-4 payload predates the ownership relocation. Its GLOBAL opcode
# names memcommit.delete_application.DirectItemDeleteRequest directly.
_LEGACY_DELETE_REQUEST_PICKLE = (
    "gASVVwAAAAAAAACMHG1lbWNvbW1pdC5kZWxldGVfYXBwbGljYXRpb26UjBdE"
    "aXJlY3RJdGVtRGVsZXRlUmVxdWVzdJSTlCmBlF2UKIwIbWVtb3J5LTGUjAVv"
    "d25lcpRlYi4="
)


@pytest.mark.parametrize(
    "legacy_name,canonical_name",
    LEGACY_AND_CANONICAL_PATHS,
)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_delete_module_identity_is_independent_of_import_order(
    legacy_name: str,
    canonical_name: str,
    legacy_first: bool,
) -> None:
    first_name, second_name = (
        (legacy_name, canonical_name) if legacy_first else (canonical_name, legacy_name)
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


def test_delete_legacy_paths_expose_the_canonical_objects() -> None:
    legacy_application = importlib.import_module("memcommit.delete_application")
    canonical_application = importlib.import_module(
        "memcommit.application.operations.delete.application"
    )
    legacy_runtime = importlib.import_module("memcommit.delete_runtime")
    canonical_runtime = importlib.import_module("memcommit.application.operations.delete.runtime")

    assert legacy_application is canonical_application
    assert (
        legacy_application.DirectItemDeleteRequest
        is canonical_application.DirectItemDeleteRequest
    )
    assert (
        legacy_application.prepare_context_delete
        is canonical_application.prepare_context_delete
    )
    assert legacy_runtime is canonical_runtime
    assert (
        legacy_runtime.MemoryStoreDeletePort is canonical_runtime.MemoryStoreDeletePort
    )
    assert (
        legacy_runtime.execute_context_delete
        is canonical_runtime.execute_context_delete
    )


@pytest.mark.parametrize(
    "relative_path",
    (
        "src/memcommit/delete_application.py",
        "src/memcommit/delete_runtime.py",
    ),
)
def test_delete_legacy_facades_contain_no_implementation(
    relative_path: str,
) -> None:
    assert_legacy_root_submodule_is_centralized(relative_path)


def test_delete_package_import_does_not_eagerly_load_implementation_modules() -> None:
    source = """
import sys
import memcommit.application.operations.delete

assert "memcommit.application.operations.delete.application" not in sys.modules
assert "memcommit.application.operations.delete.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_pre_relocation_delete_request_pickle_loads_through_legacy_alias() -> None:
    canonical = importlib.import_module("memcommit.application.operations.delete.application")

    restored = pickle.loads(base64.b64decode(_LEGACY_DELETE_REQUEST_PICKLE))

    assert restored.__class__ is canonical.DirectItemDeleteRequest
    assert restored == canonical.DirectItemDeleteRequest("memory-1", "owner")
    assert restored.__class__.__module__ == "memcommit.application.operations.delete.application"
