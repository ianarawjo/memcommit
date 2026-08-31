"""Dependency-direction contract for reusable terminal components."""

from __future__ import annotations

import ast
from pathlib import Path


ADAPTERS_ROOT = Path(__file__).parents[1] / "src" / "memcommit" / "adapters"
TERMINAL_COMPONENTS = ADAPTERS_ROOT / "console" / "terminal" / "components"
ALLOWED_CONSOLE_PRESENTATION_IMPORTS = {
    "memcommit.adapters.console.commands.search_explain.synthesize.compare.presentation",
}


def _command_imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(
                alias.name
                for alias in node.names
                if alias.name == "memcommit.adapters.console.commands"
                or alias.name.startswith("memcommit.adapters.console.commands.")
            )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "memcommit.adapters.console.commands" or module.startswith(
                "memcommit.adapters.console.commands."
            ):
                found.append(module)
    return tuple(found)


def test_terminal_components_do_not_import_command_adapters() -> None:
    violations = {
        str(path.relative_to(ADAPTERS_ROOT.parent)): tuple(
            module
            for module in imports
            if module not in ALLOWED_CONSOLE_PRESENTATION_IMPORTS
        )
        for path in sorted(TERMINAL_COMPONENTS.rglob("*.py"))
        if (imports := _command_imports(path))
        and any(
            module not in ALLOWED_CONSOLE_PRESENTATION_IMPORTS
            for module in imports
        )
    }

    assert violations == {}


def test_component_imports_resolve_to_their_canonical_objects() -> None:
    import importlib

    from memcommit.adapters.console.terminal.components.save_location import SaveLocationView as old_save
    from memcommit.adapters.console.terminal.components.semantic_viewer.detail import (
        semantic_trace_fragments as old_trace,
    )
    from memcommit.adapters.console.terminal.components.save_location import (
        SaveLocationView as new_save,
    )
    from memcommit.adapters.console.terminal.components.semantic_viewer.detail import (
        semantic_trace_fragments as new_trace,
    )

    old_table = importlib.import_module("memcommit.adapters.console.terminal.components.table")
    new_table = importlib.import_module("memcommit.adapters.console.terminal.components.table")

    assert old_table is new_table
    assert old_save is new_save
    assert old_trace is new_trace


def test_help_terminal_browser_has_one_command_owner() -> None:
    commands_root = ADAPTERS_ROOT / "console" / "commands"

    assert (commands_root / "help" / "command.py").is_file()
    assert not tuple((commands_root / "help_inventory").glob("*.py"))
    assert (TERMINAL_COMPONENTS / "session_help.py").is_file()
    assert not (ADAPTERS_ROOT / "interfaces").exists()
