"""Ownership contracts for the command-owned Atomize presentation."""

from __future__ import annotations

import ast
from pathlib import Path


REPOSITORY = Path(__file__).parents[1]
ATOMIZE_IMPACT_MODULE = (
    REPOSITORY / "src/memcommit/adapters/console/commands/semantic_updates/derive/atomize/impact.py"
)
SHARED_WORKBENCH_MODULES = (
    REPOSITORY / "src/memcommit/adapters/console/terminal/components/result/shell.py",
)


def _other_command_imports(path: Path) -> tuple[str, ...]:
    imports: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            names = (node.module,)
        elif isinstance(node, ast.Import):
            names = tuple(alias.name for alias in node.names)
        else:
            continue
        imports.extend(
            name
            for name in names
            if name.startswith("memcommit.adapters.console.commands")
            and not name.startswith("memcommit.adapters.console.commands.semantic_updates.derive.atomize")
        )
    return tuple(imports)


def test_atomize_impact_does_not_reach_through_other_commands() -> None:
    violations = _other_command_imports(ATOMIZE_IMPACT_MODULE)

    assert violations == ()


def test_atomize_legacy_interface_and_facade_paths_are_removed() -> None:
    removed = (
        REPOSITORY / "src/memcommit/adapters/interfaces/cli/atomize.py",
        REPOSITORY / "src/memcommit/adapters/interfaces/cli/atomize_grounding.py",
        REPOSITORY / "src/memcommit/adapters/console/commands/semantic_updates/derive/atomize/grounding.py",
        REPOSITORY
        / "src/memcommit/adapters/interfaces/tui/operations/atomize/__init__.py",
        REPOSITORY
        / "src/memcommit/adapters/interfaces/tui/operations/atomize/adapter.py",
        REPOSITORY
        / "src/memcommit/adapters/interfaces/tui/operations/atomize/screen.py",
        REPOSITORY
        / "src/memcommit/adapters/console/commands/semantic_updates/derive/atomize/workbench_shell.py",
        REPOSITORY
        / "src/memcommit/adapters/console/commands/semantic_updates/derive/atomize/workbench/adapter.py",
        REPOSITORY
        / "src/memcommit/adapters/console/commands/semantic_updates/derive/atomize/workbench/screen.py",
    )

    assert all(not path.exists() for path in removed)


def test_atomize_command_delegates_to_command_owned_presenters() -> None:
    source = (
        REPOSITORY / "src/memcommit/adapters/console/commands/semantic_updates/derive/atomize/command.py"
    ).read_text(encoding="utf-8")

    assert "memcommit.adapters.console.commands.semantic_updates.derive.atomize.receipt" in source
    assert "execute_atomize_in_place" in source
    assert "memcommit.adapters.console.commands.semantic_updates.derive.atomize.grounding" not in source
    assert "memcommit.adapters.interfaces.tui.operations.atomize" not in source
    assert "memcommit.adapters.interfaces.cli.atomize" not in source
    assert "prompt_toolkit" not in source


def test_impact_atomize_owns_its_analysis_view() -> None:
    source = ATOMIZE_IMPACT_MODULE.read_text(encoding="utf-8")

    assert "def run_atomize_impact_shell" in source
    assert "def render_atomize_impact_snapshot" in source
    assert "memcommit.adapters.interfaces.tui.operations.atomize" not in source


def test_atomize_impact_has_one_live_analysis_view_host() -> None:
    module = ast.parse(ATOMIZE_IMPACT_MODULE.read_text(encoding="utf-8"))
    hosts = [
        node
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "run_atomize_impact_shell"
    ]

    assert len(hosts) == 1
    assert "_run_legacy_atomize_workbench_shell" not in ATOMIZE_IMPACT_MODULE.read_text(
        encoding="utf-8"
    )


def test_result_projection_has_no_orphan_live_shell() -> None:
    source = SHARED_WORKBENCH_MODULES[0].read_text(encoding="utf-8")

    assert "def run_result_workbench_shell" not in source
    assert not (
        REPOSITORY / "src/memcommit/adapters/console/commands/result_workbench_shell.py"
    ).exists()
