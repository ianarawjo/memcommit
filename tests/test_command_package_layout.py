"""Physical layout and compatibility contracts for command packages."""

from __future__ import annotations

from importlib import import_module
import json
from pathlib import Path
import subprocess
import sys

from memcommit.compatibility.legacy_submodules import (
    LEGACY_COMMAND_SUBMODULE_ALIASES,
)


REPOSITORY = Path(__file__).resolve().parents[1]
COMMANDS = REPOSITORY / "memcommit" / "commands"
PLAN = json.loads(
    (REPOSITORY / "docs" / "command-package-layout-plan.json").read_text(
        encoding="utf-8"
    )
)


def test_commands_root_contains_only_packages() -> None:
    assert {path.name for path in COMMANDS.glob("*.py")} == {"__init__.py"}
    entry_packages = {
        entry["owner"] for entry in PLAN["modules"] if entry["role"] == "command-entry"
    }
    assert len(entry_packages) == 64
    assert {path.name for path in COMMANDS.iterdir() if path.is_dir()} >= (
        entry_packages | {"shared"}
    )
    for package in entry_packages:
        assert (COMMANDS / package / "__init__.py").is_file()
        assert (COMMANDS / package / "command.py").is_file()


def test_entry_packages_publish_only_their_declared_cli_surface() -> None:
    entries = [entry for entry in PLAN["modules"] if entry["role"] == "command-entry"]
    for entry in entries:
        package_name = entry["canonical_module"].removesuffix(".command")
        package = import_module(package_name)
        command = import_module(entry["canonical_module"])
        assert package.__all__ == entry["public_exports"]
        for exported in entry["public_exports"]:
            assert getattr(package, exported) is getattr(command, exported)


def test_flat_support_imports_resolve_to_canonical_command_modules() -> None:
    assert len(LEGACY_COMMAND_SUBMODULE_ALIASES) == 89
    program = """
from importlib import import_module

legacy = import_module("memcommit.commands.atomize_sessions")
canonical = import_module("memcommit.commands.atomize.sessions")
assert legacy is canonical
assert legacy.__spec__.name == "memcommit.commands.atomize.sessions"
"""
    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY,
        check=True,
    )
