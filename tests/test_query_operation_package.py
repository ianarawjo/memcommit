"""Package and compatibility contracts for Query's vertical operation slice."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest


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
def test_compatibility_modules_reexport_owner_symbols(compat_name, owner_name):
    compatibility = importlib.import_module(compat_name)
    owner = importlib.import_module(owner_name)

    assert compatibility.__all__ == owner.__all__
    for name in owner.__all__:
        assert getattr(compatibility, name) is getattr(owner, name)


def test_root_query_compatibility_modules_are_implementation_free():
    root = Path(__file__).parents[1] / "memcommit"
    paths = (
        root / "query_application.py",
        root / "query_runtime.py",
        root / "granted_query_application.py",
        root / "granted_query_runtime.py",
        root / "query_reference_application.py",
        root / "query_reference_runtime.py",
    )

    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert not any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            for node in ast.walk(tree)
        )
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert imported_modules
        assert all(
            module.startswith("memcommit.operations.query.")
            for module in imported_modules
        )


def test_internal_query_adapters_bypass_root_compatibility_modules():
    root = Path(__file__).parents[1] / "memcommit"
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
