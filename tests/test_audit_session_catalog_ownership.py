"""Ownership contracts for the read-only Audit session catalog."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import subprocess
import sys

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LEGACY_MODULE = "memcommit.commands.audit.sessions"
CANONICAL_MODULE = "memcommit.interfaces.tui.operations.audit.catalog"


@pytest.mark.parametrize("legacy_first", (True, False), ids=("old-first", "new-first"))
def test_audit_catalog_module_identity_is_independent_of_import_order(
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
assert legacy.audit_session_entries is canonical.audit_session_entries
"""

    subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_audit_catalog_legacy_facade_defines_no_behavior() -> None:
    source_path = REPOSITORY_ROOT / "src/memcommit/commands/audit/sessions.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))

    definitions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    canonical_imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "memcommit.interfaces.tui.operations.audit"
        and any(alias.name == "catalog" for alias in node.names)
    ]

    assert definitions == []
    assert len(canonical_imports) == 1


def test_review_consumers_import_the_interface_owner() -> None:
    for filename in ("review/command.py", "review/sessions.py"):
        source = (REPOSITORY_ROOT / "src/memcommit/commands" / filename).read_text(
            encoding="utf-8"
        )
        assert (
            "from memcommit.interfaces.tui.operations.audit.catalog import "
            "audit_session_entries"
        ) in source
        assert (
            "from memcommit.commands.audit.sessions import audit_session_entries"
            not in source
        )


def test_legacy_monkeypatch_changes_canonical_catalog_globals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = importlib.import_module(LEGACY_MODULE)
    canonical = importlib.import_module(CANONICAL_MODULE)

    sentinel = object()
    monkeypatch.setattr(legacy, "datetime", sentinel)

    assert legacy is canonical
    assert canonical.datetime is sentinel
