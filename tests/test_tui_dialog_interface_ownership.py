from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DIALOG_MODULES = (
    (
        "memcommit.adapters.console.shared.context_reach_dialog",
        "memcommit.adapters.console.tui.components.context_reach_dialog",
    ),
    (
        "memcommit.adapters.console.shared.flat_selection_dialog",
        "memcommit.adapters.console.tui.components.flat_selection_dialog",
    ),
)


@pytest.mark.parametrize("legacy_name,canonical_name", DIALOG_MODULES)
@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_dialog_module_identity_is_independent_of_import_order(
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


@pytest.mark.parametrize("legacy_name,_canonical_name", DIALOG_MODULES)
def test_legacy_dialog_facade_defines_no_behavior(
    legacy_name: str,
    _canonical_name: str,
) -> None:
    source_path = (
        REPOSITORY_ROOT.joinpath("src", *legacy_name.split(".")).with_suffix(
            ".py"
        )
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))

    definitions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]

    assert definitions == []
