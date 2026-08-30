"""Dependency gates for the operation-neutral Resolution contract."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "src" / "memcommit"


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
        "memcommit.adapters.console.commands",
        "memcommit.adapters.interfaces",
        "memcommit.merge",
        "memcommit.meld",
        "memcommit.store",
        "memcommit.providers",
        "prompt_toolkit",
        "typer",
    )
    offenders = [
        (str(path.relative_to(ROOT)), module)
        for path in (PACKAGE / "application" / "capabilities" / "resolution").glob(
            "*.py"
        )
        for module in _imports(path)
        if any(
            module == prefix or module.startswith(f"{prefix}.") for prefix in forbidden
        )
    ]

    assert offenders == []


def test_merge_application_does_not_import_an_interface_adapter():
    forbidden = (
        "memcommit.adapters.console.commands",
        "memcommit.adapters.interfaces",
        "prompt_toolkit",
        "typer",
    )
    imports = _imports(
        PACKAGE / "application" / "operations" / "merge" / "application.py"
    )

    assert not any(
        module == prefix or module.startswith(f"{prefix}.")
        for module in imports
        for prefix in forbidden
    )


def test_meld_resolution_does_not_import_runtime_or_interfaces():
    forbidden = (
        "memcommit.adapters.console.commands",
        "memcommit.adapters.interfaces",
        "memcommit.application.operations.meld.runtime",
        "memcommit.store",
        "prompt_toolkit",
        "typer",
    )
    imports = _imports(
        PACKAGE / "application" / "operations" / "meld" / "proposal_iteration.py"
    )

    assert not any(
        module == prefix or module.startswith(f"{prefix}.")
        for module in imports
        for prefix in forbidden
    )


def test_meld_interfaces_enter_the_operation_owned_resolution_boundary():
    command_imports = _imports(
        PACKAGE
        / "adapters"
        / "console"
        / "commands"
        / "meld"
        / "workflow"
        / "workflow.py"
    )
    public_imports = _imports(
        PACKAGE / "adapters" / "python_api" / "_operations" / "meld.py"
    )
    agent_imports = _imports(PACKAGE / "adapters" / "agent" / "meld.py")

    assert "memcommit.application.operations.meld.proposal_iteration" in command_imports
    assert "memcommit.application.operations.meld.proposal_iteration" in public_imports
    assert "memcommit.adapters.python_api" in agent_imports


def test_merge_cli_and_tui_depend_on_the_typed_application_contract():
    cli_imports = _imports(
        PACKAGE / "adapters" / "console" / "commands" / "merge" / "command.py"
    )
    tui_imports = _imports(
        PACKAGE
        / "adapters"
        / "console"
        / "commands"
        / "merge"
        / "workbench"
        / "conflicts.py"
    )

    assert "memcommit.application.operations.merge.application" in cli_imports
    assert "memcommit.application.operations.merge.application" in tui_imports
    assert not any(
        module.startswith("memcommit.adapters.console.commands")
        and not module.startswith("memcommit.adapters.console.commands.merge")
        for module in tui_imports
    )


def test_resolve_adapters_keep_one_application_owner():
    application_name = "memcommit.application.operations.resolve.application"
    tui_path = (
        PACKAGE
        / "adapters"
        / "console"
        / "commands"
        / "resolve"
        / "workbench"
        / "screen.py"
    )
    cli_path = PACKAGE / "adapters" / "console" / "commands" / "resolve" / "command.py"
    public_path = PACKAGE / "adapters" / "python_api" / "_operations" / "resolve.py"
    agent_path = PACKAGE / "adapters" / "agent" / "resolve.py"
    application_path = (
        PACKAGE / Path(*application_name.removeprefix("memcommit.").split("."))
    ).with_suffix(".py")
    forbidden_application_imports = (
        "memcommit.adapters.console.commands",
        "memcommit.adapters.interfaces",
        "prompt_toolkit",
        "typer",
    )
    application_imports = _imports(application_path)
    assert not any(
        module == prefix or module.startswith(f"{prefix}.")
        for module in application_imports
        for prefix in forbidden_application_imports
    )

    tui_imports = _imports(tui_path)
    cli_imports = _imports(cli_path)
    public_imports = _imports(public_path)
    agent_imports = _imports(agent_path)
    assert application_name in tui_imports
    assert application_name in cli_imports
    assert application_name in public_imports
    command_owner = application_name.split(".")[-2]
    assert not any(
        module.startswith("memcommit.adapters.console.commands")
        and not module.startswith(
            f"memcommit.adapters.console.commands.{command_owner}"
        )
        for module in tui_imports
    )
    assert not any(
        module.startswith("memcommit.adapters.console.commands")
        for module in public_imports
    )
    assert "memcommit.adapters.python_api" in agent_imports
    assert application_name not in agent_imports
    assert not any(
        module.startswith("memcommit.adapters.console.commands")
        or module.startswith("memcommit.adapters.interfaces.tui")
        for module in agent_imports
    )


def test_dedun_is_immediate_not_a_resolution_adapter():
    application_name = "memcommit.application.operations.dedun.application"
    application_path = (
        PACKAGE / Path(*application_name.removeprefix("memcommit.").split("."))
    ).with_suffix(".py")
    command_package = PACKAGE / "adapters" / "console" / "commands" / "dedun"
    execution_imports = _imports(
        PACKAGE
        / "adapters"
        / "console"
        / "commands"
        / "find_redundancies"
        / "command.py"
    )
    public_imports = _imports(
        PACKAGE / "adapters" / "python_api" / "_operations" / "dedun.py"
    )
    agent_imports = _imports(PACKAGE / "adapters" / "agent" / "dedup.py")

    assert not (command_package / "workbench.py").exists()
    assert not (command_package / "presentation.py").exists()
    assert application_name in execution_imports
    assert application_name in public_imports
    assert not any(
        module.startswith("memcommit.adapters.console.commands")
        or module.startswith("prompt_toolkit")
        or module == "typer"
        for module in _imports(application_path)
    )
    assert not any(
        module.startswith("memcommit.adapters.console.commands")
        for module in public_imports
    )
    assert "memcommit.adapters.python_api" in agent_imports
    assert application_name not in agent_imports


def test_read_report_identity_and_launcher_keep_runtime_and_ui_ownership_separate():
    identity_imports = _imports(
        PACKAGE / "application" / "capabilities" / "reviewing" / "read_report.py"
    )
    launcher_imports = _imports(
        PACKAGE
        / "adapters"
        / "console"
        / "terminal"
        / "components"
        / "read_report"
        / "launcher.py"
    )

    assert not any(
        module.startswith("memcommit.adapters.console.commands")
        or module.startswith("memcommit.adapters.interfaces")
        or module == "prompt_toolkit"
        or module.startswith("prompt_toolkit.")
        for module in identity_imports
    )
    assert (
        "memcommit.application.capabilities.reviewing.read_report" in launcher_imports
    )
    assert not any(
        module.startswith("memcommit.adapters.console.commands")
        for module in launcher_imports
    )
