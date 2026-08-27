"""Ownership and compatibility paths for the Context Init operation slice."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import subprocess
import sys

from tests.legacy_submodule_assertions import (
    assert_legacy_root_submodule_is_centralized,
)


LEGACY_AND_CANONICAL_PATHS = (
    (
        "memcommit.context_init_application",
        "memcommit.application.operations.context_init.application",
    ),
    (
        "memcommit.context_init_runtime",
        "memcommit.application.operations.context_init.runtime",
    ),
)


def test_legacy_application_path_aliases_the_operation_owned_module():
    legacy = importlib.import_module("memcommit.context_init_application")
    canonical = importlib.import_module(
        "memcommit.application.operations.context_init.application"
    )

    assert legacy is canonical
    assert legacy.ContextInitRequest is canonical.ContextInitRequest
    assert legacy.ContextInitResult is canonical.ContextInitResult
    assert legacy.ContextInitError is canonical.ContextInitError
    assert legacy.plan_context_init is canonical.plan_context_init
    assert legacy.run_context_init is canonical.run_context_init


def test_legacy_runtime_path_aliases_the_operation_owned_module():
    legacy = importlib.import_module("memcommit.context_init_runtime")
    canonical = importlib.import_module("memcommit.application.operations.context_init.runtime")

    assert legacy is canonical
    assert legacy.ContextInitSnapshot is canonical.ContextInitSnapshot
    assert legacy.prepare_context_init is canonical.prepare_context_init
    assert legacy.execute_context_init is canonical.execute_context_init
    assert legacy.MemoryStoreContextInitPort is canonical.MemoryStoreContextInitPort


def test_context_init_module_aliases_are_identity_stable_in_either_import_order():
    for legacy_name, canonical_name in LEGACY_AND_CANONICAL_PATHS:
        for first_name, second_name in (
            (legacy_name, canonical_name),
            (canonical_name, legacy_name),
        ):
            script = (
                "import importlib; "
                f"first = importlib.import_module({first_name!r}); "
                f"second = importlib.import_module({second_name!r}); "
                "assert first is second"
            )
            completed = subprocess.run(
                [sys.executable, "-c", script],
                check=False,
                capture_output=True,
                text=True,
            )

            assert completed.returncode == 0, completed.stderr


def test_context_init_legacy_facades_contain_no_implementation():
    for legacy_name, canonical_name in LEGACY_AND_CANONICAL_PATHS:
        assert_legacy_root_submodule_is_centralized(legacy_name, canonical_name)
