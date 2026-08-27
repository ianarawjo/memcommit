"""Dependency-direction contract for the shared terminal interface."""

from __future__ import annotations

import ast
from pathlib import Path


INTERFACES_ROOT = Path(__file__).parents[1] / "src" / "memcommit" / "adapters" / "interfaces"
ALLOWED_CONSOLE_PRESENTATION_IMPORTS = {
    "memcommit.adapters.console.commands.compare.presentation",
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


def test_interfaces_do_not_import_command_adapters() -> None:
    violations = {
        str(path.relative_to(INTERFACES_ROOT.parent.parent)): tuple(
            module
            for module in imports
            if module not in ALLOWED_CONSOLE_PRESENTATION_IMPORTS
        )
        for path in sorted(INTERFACES_ROOT.rglob("*.py"))
        if (imports := _command_imports(path))
        and any(
            module not in ALLOWED_CONSOLE_PRESENTATION_IMPORTS
            for module in imports
        )
    }

    assert violations == {}


def test_legacy_command_paths_preserve_interface_object_identity() -> None:
    import importlib

    from memcommit.adapters.console.commands.shared.save_location_control import SaveLocationView as old_save
    from memcommit.adapters.console.commands.shared.semantic_detail_renderer import (
        semantic_trace_fragments as old_trace,
    )
    from memcommit.adapters.console.commands.shared.session_help import SessionHelpController as old_help
    from memcommit.adapters.interfaces.tui.components.save_location import (
        SaveLocationView as new_save,
    )
    from memcommit.adapters.interfaces.tui.components.session_help import (
        SessionHelpController as new_help,
    )
    from memcommit.adapters.interfaces.tui.viewers.semantic.detail import (
        semantic_trace_fragments as new_trace,
    )

    old_inventory = importlib.import_module("memcommit.adapters.console.commands.help_inventory.command")
    new_inventory = importlib.import_module(
        "memcommit.adapters.interfaces.tui.operations.help.inventory"
    )
    old_table = importlib.import_module("memcommit.adapters.console.commands.shared.tui_table")
    new_table = importlib.import_module("memcommit.adapters.interfaces.tui.components.table")

    assert old_inventory is new_inventory
    assert old_table is new_table
    assert old_save is new_save
    assert old_help is new_help
    assert old_trace is new_trace
