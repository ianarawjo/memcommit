"""Physical layout contracts for command packages."""

from __future__ import annotations

from importlib import import_module
import json
from pathlib import Path
import subprocess
import sys


REPOSITORY = Path(__file__).resolve().parents[1]
CONSOLE = REPOSITORY / "src" / "memcommit" / "adapters" / "console"
COMMANDS = CONSOLE / "commands"
COORDINATION = CONSOLE / "coordination"
PLAN = json.loads(
    (
        REPOSITORY / "agent-records" / "docs" / "command-package-layout-plan.json"
    ).read_text(encoding="utf-8")
)


def test_commands_root_contains_only_packages() -> None:
    assert {path.name for path in COMMANDS.glob("*.py")} == {"__init__.py"}
    entry_packages = {
        entry["owner"] for entry in PLAN["modules"] if entry["role"] == "command-entry"
    }
    assert len(entry_packages) == PLAN["entry_package_count"]
    assert not (COMMANDS / "shared").exists()
    for package in entry_packages:
        package_path = COMMANDS.joinpath(*package.split("."))
        assert (package_path / "__init__.py").is_file()
        command_module = package_path / "command.py"
        command_package = package_path / "command" / "__init__.py"
        assert command_module.is_file() != command_package.is_file()


def test_multi_command_mechanisms_are_console_siblings() -> None:
    multi_command_entries = [
        entry
        for entry in PLAN["modules"]
        if entry["role"]
        in {
            "shared-command-mechanism",
            "shared-application-capability",
            "shared-context-targeting",
            "shared-terminal-component",
        }
    ]
    assert len(multi_command_entries) == PLAN["shared_module_count"]
    assert (COORDINATION / "__init__.py").is_file()
    assert not (CONSOLE / "shared").exists()
    for entry in multi_command_entries:
        module = entry["canonical_module"]
        assert module.startswith(
            (
                "memcommit.adapters.console.coordination.",
                "memcommit.adapters.console.terminal.components.",
                "memcommit.application.capabilities.",
                "memcommit.core.context_targeting.",
            )
        )
        assert import_module(module).__name__ == module


def test_entry_packages_publish_only_their_declared_cli_surface() -> None:
    entries = [entry for entry in PLAN["modules"] if entry["role"] == "command-entry"]
    for entry in entries:
        package_name = entry["canonical_module"].removesuffix(".command")
        package = import_module(package_name)
        command = import_module(entry["canonical_module"])
        assert package.__all__ == entry["public_exports"]
        for exported in entry["public_exports"]:
            assert getattr(package, exported) is getattr(command, exported)


def test_former_command_imports_are_unavailable() -> None:
    removed = [entry["legacy_module"] for entry in PLAN["modules"]]
    removed.extend(PLAN["retired_legacy_modules"])
    removed.insert(0, "memcommit.commands")
    assert len(removed) == PLAN["baseline_module_count"] + 1
    program = "\n".join(
        [
            "from importlib import import_module",
            f"removed = {removed!r}",
            "unexpected = []",
            "for module in removed:",
            "    try:",
            "        import_module(module)",
            "    except ModuleNotFoundError:",
            "        pass",
            "    else:",
            "        unexpected.append(module)",
            "assert not unexpected, unexpected",
        ]
    )
    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY,
        check=True,
    )


def test_canonical_support_module_remains_importable() -> None:
    module = import_module("memcommit.adapters.console.commands.semantic_updates.derive.atomize.records")
    assert module.__spec__.name == "memcommit.adapters.console.commands.semantic_updates.derive.atomize.records"
