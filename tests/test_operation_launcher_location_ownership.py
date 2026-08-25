"""Ownership gates for operation-launcher location discovery."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import subprocess
import sys

import pytest

from memcommit.profile_config import ProfileConfigError


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LEGACY_MODULE = "memcommit.commands.operation_launcher_location"
CANONICAL_MODULE = (
    "memcommit.interfaces.tui.components.operation_launcher.location"
)


@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_launcher_location_module_identity_is_independent_of_import_order(
    legacy_first: bool,
) -> None:
    first_name, second_name = (
        (LEGACY_MODULE, CANONICAL_MODULE)
        if legacy_first
        else (CANONICAL_MODULE, LEGACY_MODULE)
    )
    source = f"""
import importlib
import sys

first = importlib.import_module({first_name!r})
second = importlib.import_module({second_name!r})
legacy = importlib.import_module({LEGACY_MODULE!r})
canonical = importlib.import_module({CANONICAL_MODULE!r})

assert first is second
assert legacy is canonical
assert sys.modules[{LEGACY_MODULE!r}] is canonical
assert sys.modules[{CANONICAL_MODULE!r}] is canonical
"""

    subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_launcher_location_legacy_facade_defines_no_behavior() -> None:
    source_path = REPOSITORY_ROOT / "memcommit/commands/operation_launcher_location.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))

    definitions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    canonical_imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module
        == "memcommit.interfaces.tui.components.operation_launcher"
        and any(alias.name == "location" for alias in node.names)
    ]

    assert definitions == []
    assert len(canonical_imports) == 1


def test_legacy_monkeypatch_changes_canonical_location_globals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = importlib.import_module(LEGACY_MODULE)
    canonical = importlib.import_module(CANONICAL_MODULE)
    frozen_root = tmp_path / "frozen-store"

    def unavailable_registry():
        raise ProfileConfigError("unavailable")

    monkeypatch.setattr(legacy.store_module, "STORE_DIR", frozen_root)
    monkeypatch.setattr(legacy, "load_profile_registry", unavailable_registry)

    assert legacy is canonical
    assert canonical.operation_launcher_orientation().rows == (
        ("PROFILE", "(registry unavailable)"),
        ("STORE", str(frozen_root)),
    )
