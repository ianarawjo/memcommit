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
SHARED = CONSOLE / "shared"
PLAN = json.loads(
    (
        REPOSITORY
        / "agent-records"
        / "docs"
        / "command-package-layout-plan.json"
    ).read_text(encoding="utf-8")
)


def test_commands_root_contains_only_packages() -> None:
    assert {path.name for path in COMMANDS.glob("*.py")} == {"__init__.py"}
    entry_packages = {
        entry["owner"] for entry in PLAN["modules"] if entry["role"] == "command-entry"
    }
    assert len(entry_packages) == 64
    command_packages = {
        path.name
        for path in COMMANDS.iterdir()
        if path.is_dir() and not path.name.startswith("__")
    }
    assert "shared" not in command_packages
    assert command_packages >= entry_packages
    for package in command_packages:
        assert (COMMANDS / package / "__init__.py").is_file()
        assert (COMMANDS / package / "command.py").is_file()


def test_multi_command_mechanisms_are_console_siblings() -> None:
    shared_entries = [
        entry for entry in PLAN["modules"] if entry["role"] == "shared-command-mechanism"
    ]
    assert len(shared_entries) == 41
    assert (SHARED / "__init__.py").is_file()
    for entry in shared_entries:
        module = entry["canonical_module"]
        assert module.startswith("memcommit.adapters.console.shared.")
        assert (
            REPOSITORY / "src" / (module.replace(".", "/") + ".py")
        ).is_file()


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
    removed = [
        entry["legacy_module"]
        for entry in PLAN["modules"]
    ]
    removed.insert(0, "memcommit.commands")
    assert len(removed) == 154
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
    module = import_module("memcommit.adapters.console.commands.atomize.sessions")
    assert module.__spec__.name == "memcommit.adapters.console.commands.atomize.sessions"
