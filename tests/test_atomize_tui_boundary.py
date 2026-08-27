"""Dependency and compatibility contracts for the interface-owned Atomize TUI."""

from __future__ import annotations

import ast
from pathlib import Path


REPOSITORY = Path(__file__).parents[1]
INTERFACE_MODULES = (
    REPOSITORY / "src/memcommit/adapters/interfaces/tui/operations/atomize/adapter.py",
    REPOSITORY / "src/memcommit/adapters/interfaces/tui/operations/atomize/screen.py",
    REPOSITORY / "src/memcommit/adapters/interfaces/tui/workbenches/result/shell.py",
    REPOSITORY / "src/memcommit/adapters/interfaces/tui/workbenches/review/model.py",
)


def _command_imports(path: Path) -> tuple[str, ...]:
    imports: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("memcommit.commands"):
                imports.append(node.module)
        elif isinstance(node, ast.Import):
            imports.extend(
                alias.name
                for alias in node.names
                if alias.name.startswith("memcommit.commands")
            )
    return tuple(imports)


def test_atomize_tui_boundary_does_not_import_command_modules() -> None:
    violations = {
        str(path.relative_to(REPOSITORY)): _command_imports(path)
        for path in INTERFACE_MODULES
        if _command_imports(path)
    }

    assert violations == {}


def test_atomize_legacy_shell_paths_are_identity_preserving_facades() -> None:
    from memcommit.commands.atomize import render as legacy_cli
    from memcommit.commands.atomize import workbench_shell as legacy_atomize
    from memcommit.adapters.interfaces.cli import atomize as atomize_cli
    from memcommit.adapters.interfaces.tui.operations.atomize import screen as atomize_screen

    assert (
        legacy_atomize.run_atomize_workbench_shell
        is atomize_screen.run_atomize_workbench_shell
    )
    assert (
        legacy_atomize.render_atomize_workbench_snapshot
        is atomize_screen.render_atomize_workbench_snapshot
    )
    assert legacy_cli.render_atomize_impact is atomize_cli.render_atomize_impact


def test_atomize_command_delegates_terminal_presentation_to_interfaces() -> None:
    source = (
        REPOSITORY / "src/memcommit/commands/atomize/command.py"
    ).read_text(encoding="utf-8")

    assert "memcommit.adapters.interfaces.tui.operations.atomize.adapter" in source
    assert "memcommit.adapters.interfaces.cli.atomize" in source
    assert "memcommit.commands.atomize.workbench_shell" not in source
    assert "prompt_toolkit" not in source


def test_atomize_screen_has_one_live_workbench_host() -> None:
    module = ast.parse(INTERFACE_MODULES[1].read_text(encoding="utf-8"))
    hosts = [
        node
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "run_atomize_workbench_shell"
    ]

    assert len(hosts) == 1
    assert "_run_legacy_atomize_workbench_shell" not in INTERFACE_MODULES[
        1
    ].read_text(encoding="utf-8")


def test_result_projection_has_no_orphan_live_shell() -> None:
    source = INTERFACE_MODULES[2].read_text(encoding="utf-8")

    assert "def run_result_workbench_shell" not in source
    assert not (REPOSITORY / "src/memcommit/commands/result_workbench_shell.py").exists()
