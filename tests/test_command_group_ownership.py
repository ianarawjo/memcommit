"""Ownership contracts for shared Click command-group routing."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import subprocess
import sys

import click
import pytest
from typer.core import TyperGroup


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LEGACY_MODULE = "memcommit.commands.shared.command_group"
OWNER_MODULE = "memcommit.interfaces.cli.command_group"
CANONICAL_CONSUMERS = (
    "write_protection/command.py",
    "config/command.py",
    "profile/group.py",
    "dev/command.py",
    "profile/command.py",
    "shared/root_group.py",
    "semantic_eval/command.py",
)


@pytest.mark.parametrize(
    "first_name,second_name",
    ((LEGACY_MODULE, OWNER_MODULE), (OWNER_MODULE, LEGACY_MODULE)),
    ids=("old-first", "new-first"),
)
def test_command_group_module_identity_is_independent_of_import_order(
    first_name: str,
    second_name: str,
) -> None:
    source = f"""
import importlib
import sys

first = importlib.import_module({first_name!r})
second = importlib.import_module({second_name!r})
legacy = importlib.import_module({LEGACY_MODULE!r})
canonical = importlib.import_module({OWNER_MODULE!r})

assert first is second
assert legacy is canonical
assert sys.modules[{LEGACY_MODULE!r}] is canonical
assert sys.modules[{OWNER_MODULE!r}] is canonical
assert legacy.CanonicalCommandGroup is canonical.CanonicalCommandGroup
assert legacy.command_name_alias_targets is canonical.command_name_alias_targets
assert legacy.resolve_canonical_command_name is canonical.resolve_canonical_command_name
assert legacy.command_name_alias_collisions is canonical.command_name_alias_collisions
assert legacy.EXPLICIT_COMMAND_NAME_ALIASES is canonical.EXPLICIT_COMMAND_NAME_ALIASES
"""

    subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_command_group_class_and_alias_map_keep_one_identity() -> None:
    legacy = importlib.import_module(LEGACY_MODULE)
    canonical = importlib.import_module(OWNER_MODULE)

    assert legacy is canonical
    assert legacy.CanonicalCommandGroup is canonical.CanonicalCommandGroup
    assert issubclass(canonical.CanonicalCommandGroup, TyperGroup)
    assert (
        legacy.EXPLICIT_COMMAND_NAME_ALIASES is canonical.EXPLICIT_COMMAND_NAME_ALIASES
    )


def test_legacy_monkeypatch_changes_canonical_routing_globals(monkeypatch) -> None:
    legacy = importlib.import_module(LEGACY_MODULE)
    canonical = importlib.import_module(OWNER_MODULE)
    patched_aliases = {"old-spelling": "canonical-name"}

    monkeypatch.setattr(legacy, "EXPLICIT_COMMAND_NAME_ALIASES", patched_aliases)

    assert canonical.EXPLICIT_COMMAND_NAME_ALIASES is patched_aliases
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


def test_legacy_command_group_facade_defines_no_behavior() -> None:
    path = REPOSITORY_ROOT / "src" / "memcommit" / "commands" / "shared" / "command_group.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for node in ast.walk(tree)
    )
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "memcommit.interfaces.cli"
        and any(alias.name == "command_group" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert any(
        isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Subscript)
            and isinstance(target.value, ast.Attribute)
            and isinstance(target.value.value, ast.Name)
            and target.value.value.id == "sys"
            and target.value.attr == "modules"
            for target in node.targets
        )
        for node in tree.body
    )


def test_clean_command_groups_import_the_interface_owner() -> None:
    commands = REPOSITORY_ROOT / "src" / "memcommit" / "commands"

    for filename in CANONICAL_CONSUMERS:
        source = (commands / filename).read_text(encoding="utf-8")
        assert (
            "from memcommit.interfaces.cli.command_group import "
            "CanonicalCommandGroup" in source
        )
        assert "from memcommit.commands.shared.command_group import" not in source
