"""Ownership and compatibility paths for the Pwd operation slice."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import subprocess
import sys


LEGACY_AND_CANONICAL_PATHS = (
    (
        "memcommit.current_context_application",
        "memcommit.operations.pwd.application",
    ),
    (
        "memcommit.current_context_runtime",
        "memcommit.operations.pwd.runtime",
    ),
)


def test_legacy_application_path_aliases_the_operation_owned_module():
    legacy = importlib.import_module("memcommit.current_context_application")
    canonical = importlib.import_module("memcommit.operations.pwd.application")

    assert legacy is canonical
    assert legacy.get_current_context is canonical.get_current_context
    assert legacy.CurrentContextResult is canonical.CurrentContextResult
    assert legacy.CurrentContextError is canonical.CurrentContextError
    assert legacy.NoCurrentContextError is canonical.NoCurrentContextError


def test_legacy_runtime_path_aliases_the_operation_owned_module():
    legacy = importlib.import_module("memcommit.current_context_runtime")
    canonical = importlib.import_module("memcommit.operations.pwd.runtime")

    assert legacy is canonical
    assert legacy.read_current_context is canonical.read_current_context
    assert (
        legacy.MemoryStoreCurrentContextReader
        is canonical.MemoryStoreCurrentContextReader
    )


def test_pwd_module_aliases_are_identity_stable_in_either_import_order():
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


def test_pwd_legacy_facades_contain_no_function_or_class_implementation():
    repository = Path(__file__).parents[1]

    for relative_path in (
        "memcommit/current_context_application.py",
        "memcommit/current_context_runtime.py",
    ):
        source = (repository / relative_path).read_text(encoding="utf-8")
        declarations = (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
            ast.ClassDef,
        )

        assert not any(
            isinstance(node, declarations) for node in ast.walk(ast.parse(source))
        )
