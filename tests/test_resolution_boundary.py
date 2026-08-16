"""Dependency gates for the operation-neutral Resolution contract."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "memcommit"


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return tuple(modules)


def test_resolution_core_imports_no_operation_interface_or_infrastructure():
    forbidden = (
        "memcommit.commands",
        "memcommit.interfaces",
        "memcommit.merge",
        "memcommit.meld",
        "memcommit.store",
        "memcommit.providers",
        "prompt_toolkit",
        "typer",
    )
    offenders = [
        (str(path.relative_to(ROOT)), module)
        for path in (PACKAGE / "resolution").glob("*.py")
        for module in _imports(path)
        if any(
            module == prefix or module.startswith(f"{prefix}.") for prefix in forbidden
        )
    ]

    assert offenders == []


def test_merge_application_does_not_import_an_interface_adapter():
    forbidden = (
        "memcommit.commands",
        "memcommit.interfaces",
        "prompt_toolkit",
        "typer",
    )
    imports = _imports(PACKAGE / "merge_application.py")

    assert not any(
        module == prefix or module.startswith(f"{prefix}.")
        for module in imports
        for prefix in forbidden
    )


def test_meld_resolution_application_does_not_import_runtime_or_interfaces():
    forbidden = (
        "memcommit.commands",
        "memcommit.interfaces",
        "memcommit.meld_runtime",
        "memcommit.store",
        "prompt_toolkit",
        "typer",
    )
    imports = _imports(PACKAGE / "meld_resolution_application.py")

    assert not any(
        module == prefix or module.startswith(f"{prefix}.")
        for module in imports
        for prefix in forbidden
    )


def test_meld_interfaces_enter_the_operation_owned_resolution_boundary():
    command_imports = _imports(PACKAGE / "commands" / "meld.py")
    public_imports = _imports(PACKAGE / "api" / "_operations" / "meld.py")
    agent_imports = _imports(PACKAGE / "interfaces" / "agent" / "meld.py")

    assert "memcommit.meld_resolution_application" in command_imports
    assert "memcommit.meld_resolution_application" in public_imports
    assert "memcommit.api" in agent_imports


def test_merge_cli_and_tui_depend_on_the_typed_application_contract():
    cli_imports = _imports(PACKAGE / "interfaces" / "cli" / "merge.py")
    tui_imports = _imports(
        PACKAGE / "interfaces" / "tui" / "operations" / "merge" / "resolution.py"
    )

    assert "memcommit.merge_application" in cli_imports
    assert "memcommit.merge_application" in tui_imports
    assert not any(module.startswith("memcommit.commands") for module in tui_imports)
