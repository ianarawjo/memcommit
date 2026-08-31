"""Ownership checks for Ground's role-named console surfaces."""

from __future__ import annotations

import ast
from importlib import import_module
from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_CATALOG = "memcommit.adapters.console.commands.ground_workbench.ground.workspace.catalog"
FORMER_MODULES = (
    "memcommit.adapters.console.commands.ground_workbench.ground.workspace_picker",
    "memcommit.adapters.interfaces.cli.ground_workspace",
    "memcommit.adapters.interfaces.tui.operations.ground_workspace.picker",
)


def test_ground_workspace_surfaces_are_grouped_by_console_role() -> None:
    workspace = (
        REPOSITORY_ROOT / "src/memcommit/adapters/console/commands/ground_workbench/ground/workspace"
    )

    assert {
        path.relative_to(workspace).as_posix() for path in workspace.rglob("*.py")
    } == {
        "__init__.py",
        "catalog.py",
        "location.py",
        "snapshot.py",
        "viewer/__init__.py",
        "viewer/model.py",
        "viewer/screen.py",
    }
    assert not (
        REPOSITORY_ROOT
        / "src/memcommit/adapters/console/commands/ground_workbench/ground/workspace_picker.py"
    ).exists()
    assert not (
        REPOSITORY_ROOT / "src/memcommit/adapters/interfaces/cli/ground_workspace.py"
    ).exists()


def test_former_ground_workspace_adapter_modules_are_not_importable() -> None:
    source = f"""
from importlib import import_module

for module in {FORMER_MODULES!r}:
    try:
        import_module(module)
    except ModuleNotFoundError:
        pass
    else:
        raise AssertionError(module)
"""

    subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_catalog_exports_canonical_workspace_projection_objects() -> None:
    catalog = import_module(CANONICAL_CATALOG)

    assert catalog.__all__ == [
        "GroundWorkspaceDraftCatalogEntry",
        "GroundWorkspaceCatalogEntry",
        "list_ground_workspace_draft_catalog",
        "list_ground_workspace_catalog",
        "reload_selected_ground_workspace_draft",
        "reload_selected_ground_workspace",
    ]
    assert all(
        getattr(catalog, name).__module__ == CANONICAL_CATALOG
        for name in catalog.__all__
    )


def test_ground_open_workflow_imports_the_workspace_catalog_owner() -> None:
    command_path = (
        REPOSITORY_ROOT
        / "src/memcommit/adapters/console/commands/ground_workbench/ground/command/workflow/open.py"
    )
    tree = ast.parse(command_path.read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert CANONICAL_CATALOG in imported_modules
    assert not set(FORMER_MODULES) & imported_modules
