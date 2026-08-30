"""Ownership contracts for shared quality-find terminal rendering."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "src" / "memcommit"
OWNER_MODULE = "memcommit.adapters.console.terminal.components.quality_find.rendering"


def test_quality_find_render_is_the_only_physical_owner() -> None:
    owner_path = (
        PACKAGE / "adapters/console/terminal/components/quality_find/rendering.py"
    )
    tree = ast.parse(owner_path.read_text(encoding="utf-8"), filename=str(owner_path))
    functions = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert {
        "plural",
        "render_cleanup_member",
        "render_heading",
        "render_memory",
        "render_question",
        "render_readings",
        "render_reason",
    } <= functions
    assert not (PACKAGE / "adapters/console/coordination/findings_render.py").exists()
    assert not (
        PACKAGE / "adapters/console/coordination/quality_find_render.py"
    ).exists()
    assert not (PACKAGE / "adapters/interfaces/cli/quality_findings.py").exists()


def test_quality_find_commands_import_the_shared_console_owner() -> None:
    for filename in (
        "find_ambiguities/command.py",
        "find_conflicts/command.py",
        "find_duplicates/command.py",
        "find_duplicates/command.py",
    ):
        source = (PACKAGE / "adapters" / "console" / "commands" / filename).read_text(
            encoding="utf-8"
        )
        assert f"from {OWNER_MODULE} import (" in source
        assert "adapters.interfaces.cli.quality_findings" not in source
        assert "adapters.console.shared.findings_render" not in source
