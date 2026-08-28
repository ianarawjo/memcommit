"""Ownership contracts for the read-only Audit session catalog."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_MODULE = "memcommit.adapters.console.commands.audit.sessions"
RETIRED_PACKAGE = (
    REPOSITORY_ROOT
    / "src/memcommit/adapters/interfaces/tui/operations/audit"
)


def test_audit_catalog_is_implemented_by_the_command_package() -> None:
    source_path = REPOSITORY_ROOT / "src/memcommit/adapters/console/commands/audit/sessions.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))

    definitions = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    aliases = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Subscript)
            and isinstance(target.value, ast.Attribute)
            and isinstance(target.value.value, ast.Name)
            and target.value.value.id == "sys"
            and target.value.attr == "modules"
            for target in node.targets
        )
    ]

    assert {"_timestamp", "audit_session_entries"} <= definitions
    assert aliases == []
    assert "interfaces.tui.operations.audit" not in source_path.read_text(encoding="utf-8")


def test_review_consumers_import_the_command_owner() -> None:
    for filename in ("review/command.py", "review/sessions.py"):
        source = (REPOSITORY_ROOT / "src/memcommit/adapters/console/commands" / filename).read_text(
            encoding="utf-8"
        )
        assert (
            "from memcommit.adapters.console.commands.audit.sessions import "
            "audit_session_entries"
        ) in source
        assert "interfaces.tui.operations.audit" not in source


def test_retired_audit_interface_package_has_no_python_facade() -> None:
    assert not tuple(RETIRED_PACKAGE.glob("*.py"))


def test_catalog_monkeypatch_targets_the_command_owned_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical = importlib.import_module(CANONICAL_MODULE)

    sentinel = object()
    monkeypatch.setattr(canonical, "datetime", sentinel)

    assert canonical.datetime is sentinel
