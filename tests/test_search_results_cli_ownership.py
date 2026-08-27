"""Ownership contracts for the interface-owned search-result presenter."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import subprocess
import sys

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LEGACY_MODULE = "memcommit.commands.find.result_present"
OWNER_MODULE = "memcommit.adapters.interfaces.cli.search_results"


@pytest.mark.parametrize(
    "first_name,second_name",
    ((LEGACY_MODULE, OWNER_MODULE), (OWNER_MODULE, LEGACY_MODULE)),
    ids=("old-first", "new-first"),
)
def test_search_result_presenter_identity_is_independent_of_import_order(
    first_name: str,
    second_name: str,
) -> None:
    source = f"""
import importlib
import sys

first = importlib.import_module({first_name!r})
second = importlib.import_module({second_name!r})
legacy = importlib.import_module({LEGACY_MODULE!r})
canonical = importlib.import_module({OWNER_MODULE!r})

assert first is second
assert legacy is canonical
assert sys.modules[{LEGACY_MODULE!r}] is canonical
assert sys.modules[{OWNER_MODULE!r}] is canonical
assert "__all__" not in canonical.__dict__
assert {{name for name in legacy.__dict__ if not name.startswith("_")}} == {{
    name for name in canonical.__dict__ if not name.startswith("_")
}}
"""

    subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_search_result_presenter_legacy_path_is_the_canonical_module() -> None:
    legacy = importlib.import_module(LEGACY_MODULE)
    canonical = importlib.import_module(OWNER_MODULE)

    assert legacy is canonical
    assert legacy.SearchResultViewRow is canonical.SearchResultViewRow
    assert legacy.SearchResultGroup is canonical.SearchResultGroup
    assert legacy.group_search_items is canonical.group_search_items
    assert (
        legacy.render_grouped_search_results
        is canonical.render_grouped_search_results
    )


def test_search_result_presenter_legacy_facade_defines_no_behavior() -> None:
    source_path = REPOSITORY_ROOT / "src/memcommit/commands/find/result_present.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))

    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for node in ast.walk(tree)
    )
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "memcommit.adapters.interfaces.cli"
        and any(alias.name == "search_results" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert any(
        isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Subscript)
            and isinstance(target.value, ast.Attribute)
            and isinstance(target.value.value, ast.Name)
            and target.value.value.id == "sys"
            and target.value.attr == "modules"
            for target in node.targets
        )
        for node in tree.body
    )
