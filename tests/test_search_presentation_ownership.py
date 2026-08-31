"""Ownership contracts for Search's command-owned result presenter."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
OWNER_MODULE = "memcommit.adapters.console.commands.search_explain.retrieve_answer.search.result_present"
REMOVED_MODULE = "memcommit.adapters.interfaces.cli.search_results"


def test_search_result_presenter_is_owned_by_the_search_command() -> None:
    owner = importlib.import_module(OWNER_MODULE)

    assert owner.SearchResultViewRow.__module__ == OWNER_MODULE
    assert owner.SearchResultGroup.__module__ == OWNER_MODULE
    assert owner.group_search_items.__module__ == OWNER_MODULE
    assert owner.render_grouped_search_results.__module__ == OWNER_MODULE


def test_removed_interface_presenter_has_no_compatibility_facade() -> None:
    removed_path = (
        REPOSITORY_ROOT / "src/memcommit/adapters/interfaces/cli/search_results.py"
    )

    assert not removed_path.exists()
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(REMOVED_MODULE)


def test_search_presenter_owner_contains_the_behavior() -> None:
    source_path = (
        REPOSITORY_ROOT
        / "src/memcommit/adapters/console/commands/search_explain/retrieve_answer/search/result_present.py"
    )
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    definitions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }

    assert {
        "SearchResultViewRow",
        "SearchResultGroup",
        "group_search_items",
        "group_search_result_rows",
        "render_grouped_search_results",
    } <= definitions
    assert REMOVED_MODULE not in source
