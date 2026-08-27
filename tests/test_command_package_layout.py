"""Physical layout contracts for command packages."""

from __future__ import annotations

from importlib import import_module
import json
from pathlib import Path
import subprocess
import sys


REPOSITORY = Path(__file__).resolve().parents[1]
COMMANDS = REPOSITORY / "src" / "memcommit" / "commands"
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


def test_flat_support_imports_are_unavailable() -> None:
    removed = [
        entry["legacy_module"]
        for entry in PLAN["modules"]
        if entry["role"] != "command-entry"
    ]
    assert len(removed) == 89
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
    module = import_module("memcommit.commands.atomize.sessions")
    assert module.__spec__.name == "memcommit.commands.atomize.sessions"
