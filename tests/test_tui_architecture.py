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


def test_summarize_operation_tui_only_composes_shared_workbench() -> None:
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
    assert any(
        module == "memcommit.interfaces.tui.workbenches.context_summary"
        for path in operation_dir.rglob("*.py")
        for module in _imports(path)
    )


def test_moved_component_symbols_no_longer_live_in_tui_primitives() -> None:
    tree = ast.parse(
        (PACKAGE / "commands" / "shared" / "tui_primitives.py").read_text()
    )
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
        "FramedMultilineInput",
        "InFrameInputManager",
        "InFrameInputSection",
        "build_framed_multiline_input",
        "build_inline_direct_edit_input",
    }

    assert definitions.isdisjoint(moved)


def test_no_consumer_reaches_moved_input_symbols_through_legacy_primitives() -> None:
    moved = {
        "FramedMultilineInput",
        "InFrameInputManager",
        "InFrameInputSection",
        "build_framed_multiline_input",
        "build_inline_direct_edit_input",
        "classify_inline_edit_submission",
    }
    offenders: list[tuple[str, str]] = []
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module != "memcommit.commands.shared.tui_primitives":
                continue
            offenders.extend(
                (str(path.relative_to(ROOT)), alias.name)
                for alias in node.names
                if alias.name in moved
            )

    assert offenders == []


def test_add_tui_delegates_common_interaction_mechanics() -> None:
    path = PACKAGE / "interfaces" / "tui" / "operations" / "add" / "screen.py"
    source = path.read_text()
    imports = set(_imports(path))

    assert {
        "memcommit.context_targeting.tui.selector",
        "memcommit.interfaces.tui.components.focus",
        "memcommit.interfaces.tui.components.frame",
        "memcommit.interfaces.tui.components.in_frame_input",
        "memcommit.interfaces.tui.components.multiline_input",
        "memcommit.interfaces.tui.components.scrollable_pane",
    } <= imports
    assert ".vertical_scroll" not in source
    assert "ScrollbarMargin" not in source
    assert "TextArea(" not in source


def test_direct_memory_actions_share_one_selector_composition() -> None:
    owner = PACKAGE / "context_targeting" / "tui" / "direct_memory_selector.py"
    owner_imports = set(_imports(owner))

    assert {
        "memcommit.context_targeting.tui.memory_selection",
        "memcommit.context_targeting.tui.picker",
        "memcommit.context_targeting.tui.selector",
    } <= owner_imports

    consumers = (
        PACKAGE / "interfaces" / "tui" / "operations" / "edit" / "screen.py",
        PACKAGE / "interfaces" / "tui" / "operations" / "embed" / "screen.py",
        PACKAGE / "interfaces" / "tui" / "operations" / "reference" / "screen.py",
    )
    for path in consumers:
        imports = set(_imports(path))
        source = path.read_text()
        assert "memcommit.context_targeting.tui.direct_memory_selector" in imports
        assert "ContextMemoryPreviewController(" not in source
        assert "DirectMemorySelectionState(" not in source
