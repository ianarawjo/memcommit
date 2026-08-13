"""Mechanical gates for the incremental TUI component migration."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "memcommit"


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text())
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
        elif isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
    return tuple(modules)


def test_interfaces_never_import_command_adapters() -> None:
    offenders = [
        str(path.relative_to(ROOT))
        for path in (PACKAGE / "interfaces").rglob("*.py")
        if any(module.startswith("memcommit.commands") for module in _imports(path))
    ]

    assert offenders == []


def test_migrated_tui_modules_have_no_legacy_import_path() -> None:
    retired = {
        "memcommit.commands.tui_text_layout",
        "memcommit.commands.surface_focus",
        "memcommit.commands.semantic_viewer",
        "memcommit.commands.read_only_viewer",
        "memcommit.commands.understanding_render",
    }
    offenders = [
        (str(path.relative_to(ROOT)), module)
        for path in PACKAGE.rglob("*.py")
        for module in _imports(path)
        if module in retired
    ]

    assert offenders == []
    assert all(
        not (ROOT / (module.replace(".", "/") + ".py")).exists() for module in retired
    )


def test_summarize_operation_tui_only_composes_shared_viewer() -> None:
    operation_dir = PACKAGE / "interfaces" / "tui" / "operations" / "summarize"
    forbidden = {
        "prompt_toolkit.application",
        "prompt_toolkit.layout",
        "prompt_toolkit.widgets",
        "memcommit.interfaces.cli",
    }
    offenders = [
        (str(path.relative_to(ROOT)), module)
        for path in operation_dir.rglob("*.py")
        for module in _imports(path)
        if any(module.startswith(prefix) for prefix in forbidden)
    ]

    assert offenders == []


def test_moved_component_symbols_no_longer_live_in_tui_primitives() -> None:
    tree = ast.parse((PACKAGE / "commands" / "tui_primitives.py").read_text())
    definitions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }
    moved = {
        "TuiRegion",
        "ScrollableTextPane",
        "ScrollableFormattedTextPane",
        "WrappedScrollbarMargin",
        "bind_focused_frame_style",
        "build_focused_frame",
        "build_tui_frame",
        "build_scrollable_text_pane",
        "build_scrollable_formatted_text_pane",
        "move_wrapped_read_cursor",
        "scroll_wrapped_page",
        "set_scrollable_pane_text",
    }

    assert definitions.isdisjoint(moved)
