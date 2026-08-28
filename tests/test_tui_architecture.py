"""Mechanical gates for the incremental TUI component migration."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "src" / "memcommit"
CONSOLE_TUI = PACKAGE / "adapters" / "console" / "tui"
ALLOWED_COMMAND_PRESENTATION_IMPORTS = {
    "memcommit.adapters.console.commands.compare.presentation",
}


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text())
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
        elif isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
    return tuple(modules)


def test_core_and_components_have_one_console_tui_owner() -> None:
    legacy_root = PACKAGE / "adapters" / "interfaces" / "tui"

    assert (CONSOLE_TUI / "core" / "__init__.py").is_file()
    assert (CONSOLE_TUI / "components" / "__init__.py").is_file()
    assert not (legacy_root / "core").exists()
    assert not (legacy_root / "components").exists()

    retired = (
        "memcommit.adapters.interfaces.tui.core",
        "memcommit.adapters.interfaces.tui.components",
    )
    offenders = [
        (str(path.relative_to(ROOT)), module)
        for path in PACKAGE.rglob("*.py")
        for module in _imports(path)
        if any(
            module == prefix or module.startswith(f"{prefix}.") for prefix in retired
        )
    ]

    assert offenders == []


def test_console_tui_core_does_not_reach_up_into_components() -> None:
    offenders = [
        (str(path.relative_to(ROOT)), module)
        for path in (CONSOLE_TUI / "core").rglob("*.py")
        for module in _imports(path)
        if module == "memcommit.adapters.console.tui.components"
        or module.startswith("memcommit.adapters.console.tui.components.")
    ]

    assert offenders == []


def test_interfaces_never_import_command_adapters() -> None:
    offenders = [
        str(path.relative_to(ROOT))
        for path in (PACKAGE / "adapters" / "interfaces").rglob("*.py")
        if any(
            module.startswith("memcommit.adapters.console.commands")
            and module not in ALLOWED_COMMAND_PRESENTATION_IMPORTS
            for module in _imports(path)
        )
    ]

    assert offenders == []


def test_migrated_tui_modules_have_no_legacy_import_path() -> None:
    retired = {
        "memcommit.adapters.console.commands.tui_text_layout",
        "memcommit.adapters.console.commands.surface_focus",
        "memcommit.adapters.console.commands.semantic_viewer",
        "memcommit.adapters.console.commands.read_only_viewer",
        "memcommit.adapters.console.commands.understanding_render",
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


def test_summarize_command_tui_only_composes_shared_workbench() -> None:
    workbench_dir = (
        PACKAGE / "adapters" / "console" / "commands" / "summarize" / "workbench"
    )
    forbidden = {
        "prompt_toolkit.application",
        "prompt_toolkit.layout",
        "prompt_toolkit.widgets",
        "memcommit.adapters.interfaces.cli",
    }
    offenders = [
        (str(path.relative_to(ROOT)), module)
        for path in workbench_dir.rglob("*.py")
        for module in _imports(path)
        if any(module.startswith(prefix) for prefix in forbidden)
    ]

    assert offenders == []
    assert any(
        module == "memcommit.adapters.interfaces.tui.workbenches.context_summary"
        for path in workbench_dir.rglob("*.py")
        for module in _imports(path)
    )


def test_moved_component_symbols_no_longer_live_in_tui_primitives() -> None:
    tree = ast.parse(
        (PACKAGE / "adapters" / "console" / "shared" / "tui_primitives.py").read_text()
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
            if node.module != "memcommit.adapters.console.shared.tui_primitives":
                continue
            offenders.extend(
                (str(path.relative_to(ROOT)), alias.name)
                for alias in node.names
                if alias.name in moved
            )

    assert offenders == []


def test_add_tui_delegates_common_interaction_mechanics() -> None:
    path = (
        PACKAGE
        / "adapters"
        / "console"
        / "commands"
        / "add"
        / "workbench"
        / "screen.py"
    )
    source = path.read_text()
    imports = set(_imports(path))

    assert {
        "memcommit.core.context_targeting.tui.selector",
        "memcommit.adapters.console.tui.components.focus",
        "memcommit.adapters.console.tui.components.frame",
        "memcommit.adapters.console.tui.components.in_frame_input",
        "memcommit.adapters.console.tui.components.multiline_input",
        "memcommit.adapters.console.tui.components.scrollable_pane",
    } <= imports
    assert ".vertical_scroll" not in source
    assert "ScrollbarMargin" not in source
    assert "TextArea(" not in source


def test_direct_memory_actions_share_one_selector_composition() -> None:
    owner = PACKAGE / "core" / "context_targeting" / "tui" / "direct_memory_selector.py"
    owner_imports = set(_imports(owner))

    assert {
        "memcommit.core.context_targeting.tui.memory_selection",
        "memcommit.core.context_targeting.tui.picker",
        "memcommit.core.context_targeting.tui.selector",
    } <= owner_imports

    reference_candidates = (
        PACKAGE
        / "adapters"
        / "console"
        / "commands"
        / "reference"
        / "workbench"
        / "screen.py",
        PACKAGE
        / "adapters"
        / "interfaces"
        / "tui"
        / "operations"
        / "reference"
        / "screen.py",
    )
    reference_screens = tuple(path for path in reference_candidates if path.is_file())
    assert len(reference_screens) == 1

    consumers = (
        PACKAGE
        / "adapters"
        / "console"
        / "commands"
        / "edit"
        / "workbench"
        / "screen.py",
        PACKAGE
        / "adapters"
        / "console"
        / "commands"
        / "embed"
        / "workbench"
        / "screen.py",
        reference_screens[0],
    )
    for path in consumers:
        imports = set(_imports(path))
        source = path.read_text()
        assert "memcommit.core.context_targeting.tui.direct_memory_selector" in imports
        assert "ContextMemoryPreviewController(" not in source
        assert "DirectMemorySelectionState(" not in source
