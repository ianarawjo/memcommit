"""Mechanical gates for the terminal component architecture."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "src" / "memcommit"
CONSOLE_TERMINAL = PACKAGE / "adapters" / "console" / "terminal"
ALLOWED_COMMAND_PRESENTATION_IMPORTS = {
    "memcommit.adapters.console.commands.search_explain.synthesize.compare.presentation",
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


def test_core_and_components_have_one_terminal_owner() -> None:
    assert (CONSOLE_TERMINAL / "core" / "__init__.py").is_file()
    assert (CONSOLE_TERMINAL / "components" / "__init__.py").is_file()
    assert not (PACKAGE / "adapters" / "console" / "tui").exists()
    assert not (PACKAGE / "adapters" / "interfaces").exists()

    retired = (
        "memcommit.adapters.console.tui",
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


def test_operation_specific_terminal_adapters_are_command_owned() -> None:
    legacy_operations = PACKAGE / "adapters" / "interfaces" / "tui" / "operations"

    assert not legacy_operations.exists()
    offenders = [
        (str(path.relative_to(ROOT)), module)
        for path in PACKAGE.rglob("*.py")
        for module in _imports(path)
        if module.startswith("memcommit.adapters.interfaces.tui.operations")
    ]

    assert offenders == []


def test_terminal_core_does_not_reach_up_into_components() -> None:
    offenders = [
        (str(path.relative_to(ROOT)), module)
        for path in (CONSOLE_TERMINAL / "core").rglob("*.py")
        for module in _imports(path)
        if module == "memcommit.adapters.console.terminal.components"
        or module.startswith("memcommit.adapters.console.terminal.components.")
    ]

    assert offenders == []


def test_terminal_components_never_import_command_adapters() -> None:
    offenders = [
        str(path.relative_to(ROOT))
        for path in (CONSOLE_TERMINAL / "components").rglob("*.py")
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
        PACKAGE
        / "adapters"
        / "console"
        / "commands"
        / "search_explain"
        / "synthesize"
        / "summarize"
        / "workbench"
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
        module == "memcommit.adapters.console.terminal.components.context_summary"
        for path in workbench_dir.rglob("*.py")
        for module in _imports(path)
    )


def test_moved_component_symbols_no_longer_live_in_tui_primitives() -> None:
    tree = ast.parse((CONSOLE_TERMINAL / "components" / "primitives.py").read_text())
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
            if (
                node.module
                != "memcommit.adapters.console.terminal.components.primitives"
            ):
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
        "memcommit.adapters.console.terminal.components.operation_context_scope_editor.existing_context_selector",
        "memcommit.adapters.console.terminal.components.focus",
        "memcommit.adapters.console.terminal.components.frame",
        "memcommit.adapters.console.terminal.components.in_frame_input",
        "memcommit.adapters.console.terminal.components.multiline_input",
        "memcommit.adapters.console.terminal.components.scrollable_pane",
    } <= imports
    assert ".vertical_scroll" not in source
    assert "ScrollbarMargin" not in source
    assert "TextArea(" not in source


def test_direct_memory_actions_share_one_selector_composition() -> None:
    owner = (
        PACKAGE
        / "adapters"
        / "console"
        / "terminal"
        / "components"
        / "operation_context_scope_editor"
        / "direct_memory_selector.py"
    )
    owner_imports = set(_imports(owner))

    assert {
        "memcommit.adapters.console.terminal.components.operation_context_scope_editor.state.memory_selection",
        "memcommit.adapters.console.terminal.components.context_picker.model",
        "memcommit.adapters.console.terminal.components.context_picker.preview",
        "memcommit.adapters.console.terminal.components.operation_context_scope_editor.existing_context_selector",
    } <= owner_imports

    reference_screen = (
        PACKAGE
        / "adapters"
        / "console"
        / "commands"
        / "reference"
        / "workbench"
        / "screen.py"
    )
    assert reference_screen.is_file()

    consumers = (
        PACKAGE
        / "adapters"
        / "console"
        / "commands"
        / "direct_changes"
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
        reference_screen,
    )
    for path in consumers:
        imports = set(_imports(path))
        source = path.read_text()
        assert (
            "memcommit.adapters.console.terminal.components.operation_context_scope_editor.direct_memory_selector"
            in imports
        )
        assert "ContextMemoryPreviewController(" not in source
        assert "DirectMemorySelectionState(" not in source


def test_context_picker_is_owned_by_the_terminal_adapter() -> None:
    legacy_owner = PACKAGE / "core" / "context_targeting" / "tui" / "picker.py"
    package = (
        PACKAGE / "adapters" / "console" / "terminal" / "components" / "context_picker"
    )
    public_api = package / "__init__.py"
    model = package / "model.py"
    preview = package / "preview.py"
    projection = package / "projection.py"
    rendering = package / "rendering.py"
    dialog = package / "dialog.py"

    assert not legacy_owner.exists()
    assert public_api.is_file()
    assert model.is_file()
    assert preview.is_file()
    assert projection.is_file()
    assert rendering.is_file()
    assert dialog.is_file()
    assert "def choose_context(" not in public_api.read_text()
    assert "def choose_context(" not in rendering.read_text()
    assert "def choose_context(" in dialog.read_text()
    assert "class ContextMemoryRow" in model.read_text()
    assert "def context_memory_rows(" in projection.read_text()
    assert "class ContextMemoryPreviewController" in preview.read_text()
    assert "def render_context_options(" in rendering.read_text()
    assert "Application(" not in model.read_text()
    assert "Application(" not in projection.read_text()
    assert "Application(" not in preview.read_text()
    assert "Application(" not in rendering.read_text()
    assert "Application(" in dialog.read_text()

    legacy_import = "memcommit.core.context_targeting.tui.picker"
    offenders = tuple(
        str(path.relative_to(ROOT))
        for path in (*PACKAGE.rglob("*.py"), *(ROOT / "tests").rglob("*.py"))
        if path != Path(__file__) and legacy_import in path.read_text()
    )
    assert offenders == ()
