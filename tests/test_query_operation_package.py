"""Package and compatibility contracts for Query's vertical operation slice."""

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


_MODULE_PAIRS = (
    ("memcommit.query_application", "memcommit.operations.query.ordinary_application"),
    ("memcommit.query_runtime", "memcommit.operations.query.ordinary_runtime"),
    (
        "memcommit.granted_query_application",
        "memcommit.operations.query.granted_application",
    ),
    ("memcommit.granted_query_runtime", "memcommit.operations.query.granted_runtime"),
    (
        "memcommit.query_reference_application",
        "memcommit.operations.query.reference_application",
    ),
    (
        "memcommit.query_reference_runtime",
        "memcommit.operations.query.reference_runtime",
    ),
)


@pytest.mark.parametrize(("compat_name", "owner_name"), _MODULE_PAIRS)
@pytest.mark.parametrize("compat_first", (True, False), ids=("old-first", "new-first"))
def test_query_module_identity_is_independent_of_import_order(
    compat_name: str,
    owner_name: str,
    compat_first: bool,
) -> None:
    first_name, second_name = (
        (compat_name, owner_name)
        if compat_first
        else (owner_name, compat_name)
    )
    program = f"""
import importlib
import sys

first = importlib.import_module({first_name!r})
second = importlib.import_module({second_name!r})
compatibility = importlib.import_module({compat_name!r})
owner = importlib.import_module({owner_name!r})

assert first is second
assert compatibility is owner
assert sys.modules[{compat_name!r}] is owner
assert sys.modules[{owner_name!r}] is owner
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=Path(__file__).parents[1],
        check=True,
    )


@pytest.mark.parametrize(("compat_name", "owner_name"), _MODULE_PAIRS)
def test_compatibility_modules_are_their_owner(compat_name, owner_name):
    compatibility = importlib.import_module(compat_name)
    owner = importlib.import_module(owner_name)

    assert compatibility is owner
    assert compatibility.__all__ == owner.__all__
    for name in owner.__all__:
        assert getattr(compatibility, name) is getattr(owner, name)


def test_root_query_compatibility_modules_are_implementation_free():
    for legacy_name, canonical_name in _MODULE_PAIRS:
        assert_legacy_root_submodule_is_centralized(
            legacy_name,
            canonical_name,
        )


def test_query_operation_package_import_is_lazy():
    program = """
import sys
import memcommit.operations.query

blocked = (
    "memcommit.operations.query.ordinary_application",
    "memcommit.operations.query.ordinary_runtime",
    "memcommit.operations.query.granted_application",
    "memcommit.operations.query.granted_runtime",
    "memcommit.operations.query.reference_application",
    "memcommit.operations.query.reference_runtime",
)
assert not any(name in sys.modules for name in blocked)
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=Path(__file__).parents[1],
        check=True,
    )


@pytest.mark.parametrize(
    ("compat_name", "owner_name", "global_name"),
    (
        (
            "memcommit.query_application",
            "memcommit.operations.query.ordinary_application",
            "OrdinaryQueryRequest",
        ),
        (
            "memcommit.query_runtime",
            "memcommit.operations.query.ordinary_runtime",
            "MemoryStoreOrdinaryQuerySourcePort",
        ),
        (
            "memcommit.granted_query_application",
            "memcommit.operations.query.granted_application",
            "GrantedQueryRequest",
        ),
        (
            "memcommit.granted_query_runtime",
            "memcommit.operations.query.granted_runtime",
            "MemoryStoreGrantedQueryReadPort",
        ),
        (
            "memcommit.query_reference_application",
            "memcommit.operations.query.reference_application",
            "QueryReferenceRequest",
        ),
        (
            "memcommit.query_reference_runtime",
            "memcommit.operations.query.reference_runtime",
            "MemoryStoreQueryReferenceSourcePort",
        ),
    ),
)
def test_pre_relocation_query_globals_load_through_aliases(
    compat_name: str,
    owner_name: str,
    global_name: str,
) -> None:
    owner = importlib.import_module(owner_name)
    payload = f"c{compat_name}\n{global_name}\n.".encode()

    assert pickle.loads(payload) is getattr(owner, global_name)


def test_internal_query_adapters_bypass_root_compatibility_modules():
    root = Path(__file__).parents[1] / "src" / "memcommit"
    compatibility_modules = {
        "memcommit.query_application",
        "memcommit.query_runtime",
        "memcommit.granted_query_application",
        "memcommit.granted_query_runtime",
        "memcommit.query_reference_application",
        "memcommit.query_reference_runtime",
    }
    compatibility_paths = {
        root / "query_application.py",
        root / "query_runtime.py",
        root / "granted_query_application.py",
        root / "granted_query_runtime.py",
        root / "query_reference_application.py",
        root / "query_reference_runtime.py",
    }

    violations: list[tuple[Path, str]] = []
    for path in root.rglob("*.py"):
        if path in compatibility_paths:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in compatibility_modules:
                violations.append((path.relative_to(root), node.module))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in compatibility_modules:
                        violations.append((path.relative_to(root), alias.name))

    assert violations == []


def test_command_owned_query_execution_facade_is_retired():
    root = Path(__file__).parents[1] / "src" / "memcommit"

    assert not (root / "commands" / "query_execution.py").exists()
    violations: list[Path] = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "memcommit.commands.query_execution"
            ):
                violations.append(path.relative_to(root))
            elif isinstance(node, ast.Import) and any(
                alias.name == "memcommit.commands.query_execution"
                for alias in node.names
            ):
                violations.append(path.relative_to(root))

    assert violations == []
