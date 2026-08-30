"""Ownership contracts for coordinated Click command-group routing."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import click
import pytest
from typer.core import TyperGroup


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
OWNER_MODULE = "memcommit.adapters.console.coordination.command_group"
OWNER_PATH = (
    REPOSITORY_ROOT
    / "src"
    / "memcommit"
    / "adapters"
    / "console"
    / "coordination"
    / "command_group.py"
)
REMOVED_INTERFACE_PATH = (
    REPOSITORY_ROOT
    / "src"
    / "memcommit"
    / "adapters"
    / "interfaces"
    / "cli"
    / "command_group.py"
)
CANONICAL_CONSUMERS = (
    "commands/config/command.py",
    "commands/dev/command.py",
    "commands/impact/command.py",
    "commands/profile/command.py",
    "commands/profile/group.py",
    "commands/provider/command.py",
    "commands/eval/command.py",
    "commands/write_protection/command.py",
    "coordination/root_group.py",
)


def test_console_coordination_command_group_is_the_only_implementation_owner() -> None:
    tree = ast.parse(OWNER_PATH.read_text(encoding="utf-8"), filename=str(OWNER_PATH))

    assert any(isinstance(node, ast.ClassDef) for node in tree.body)
    assert any(isinstance(node, ast.FunctionDef) for node in tree.body)
    assert not REMOVED_INTERFACE_PATH.exists()
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("memcommit.adapters.interfaces.cli.command_group")


def test_command_group_class_and_alias_map_keep_one_identity() -> None:
    canonical = importlib.import_module(OWNER_MODULE)
    imported_again = importlib.import_module(OWNER_MODULE)

    assert canonical is imported_again
    assert issubclass(canonical.CanonicalCommandGroup, TyperGroup)
    assert (
        canonical.EXPLICIT_COMMAND_NAME_ALIASES
        is imported_again.EXPLICIT_COMMAND_NAME_ALIASES
    )


def test_canonical_monkeypatch_changes_routing_globals(monkeypatch) -> None:
    canonical = importlib.import_module(OWNER_MODULE)
    patched_aliases = {"old-spelling": "canonical-name"}

    monkeypatch.setattr(canonical, "EXPLICIT_COMMAND_NAME_ALIASES", patched_aliases)

    assert canonical.command_name_alias_targets(("canonical-name",)) == {
        "old-spelling": ("canonical-name",),
        "oldspelling": ("canonical-name",),
        "canonicalname": ("canonical-name",),
    }


def test_command_group_error_contract_keeps_exit_and_suggestion_order() -> None:
    canonical = importlib.import_module(OWNER_MODULE)
    group = canonical.CanonicalCommandGroup(name="mem")
    for name in ("find-redundancies", "find-duplicates", "find-ambiguities"):
        group.add_command(click.Command(name=name))
    context = click.Context(group)

    with pytest.raises(click.UsageError) as raised:
        group.resolve_command(context, ["find-redundancie"])

    assert raised.value.exit_code == 2
    assert raised.value.message == (
        "No such command 'find-redundancie'. Did you mean one of: "
        "'find-redundancies', 'find-duplicates'?"
    )


def test_all_command_groups_import_the_console_coordination_owner() -> None:
    console = REPOSITORY_ROOT / "src" / "memcommit" / "adapters" / "console"

    for filename in CANONICAL_CONSUMERS:
        source = (console / filename).read_text(encoding="utf-8")
        assert (
            "from memcommit.adapters.console.coordination.command_group import "
            "CanonicalCommandGroup" in source
        )
        assert "memcommit.adapters.interfaces.cli.command_group" not in source
