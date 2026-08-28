"""Canonical command identity with conservative user-input aliases."""

from __future__ import annotations

import click
import pytest
from typer.main import get_command
from typer.testing import CliRunner

from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.coordination.command_group import (
    CanonicalCommandGroup,
    command_name_alias_collisions,
    resolve_canonical_command_name,
)


runner = CliRunner(mix_stderr=False)


@pytest.mark.parametrize(
    ("entered", "canonical"),
    (
        ("initstudy", "init-study"),
        ("checkconformance", "check-conformance"),
        ("findredundancies", "find-redundancies"),
        ("find-redundancy", "find-redundancies"),
        ("findredundancy", "find-redundancies"),
        ("find-duplicate", "find-duplicates"),
        ("findduplicate", "find-duplicates"),
        ("find-ambiguity", "find-ambiguities"),
        ("findambiguity", "find-ambiguities"),
        ("find-conflict", "find-conflicts"),
        ("findconflict", "find-conflicts"),
    ),
)
def test_root_aliases_open_canonical_help(entered, canonical):
    result = runner.invoke(app, [entered, "--help"])

    assert result.exit_code == 0, result.output
    assert f" {canonical} " in result.output.splitlines()[1]


def test_hyphen_omission_applies_to_nested_command_groups():
    profile_result = runner.invoke(app, ["profile", "archivestudy", "--help"])
    dev_result = runner.invoke(
        app,
        ["dev", "querysource", "install", "--help"],
    )

    assert profile_result.exit_code == 0, profile_result.output
    assert " profile archive-study " in profile_result.output.splitlines()[1]
    assert dev_result.exit_code == 0, dev_result.output
    assert " dev query-source install " in dev_result.output.splitlines()[1]


def test_underscore_is_not_an_accepted_command_separator():
    result = runner.invoke(app, ["init_study", "--help"])

    assert result.exit_code == 2
    assert "No such command 'init_study'" in result.stderr
    assert "Did you mean 'init-study'?" in result.stderr


def test_unknown_command_suggests_but_does_not_execute():
    result = runner.invoke(app, ["find-redundancie", "--help"])

    assert result.exit_code == 2
    assert "No such command 'find-redundancie'" in result.stderr
    assert "'find-redundancies'" in result.stderr


def test_aliases_are_not_registered_as_help_operations():
    root = get_command(app)
    context = click.Context(root)
    try:
        assert root.get_command(context, "initstudy") is None
        assert root.get_command(context, "find-redundancy") is None
    finally:
        context.close()


def test_every_command_group_uses_collision_free_shared_routing():
    root = get_command(app)

    def visit(group):
        assert isinstance(group, CanonicalCommandGroup)
        assert command_name_alias_collisions(group.commands) == {}
        for name in group.commands:
            if "-" in name:
                assert resolve_canonical_command_name(
                    name.replace("-", ""),
                    group.commands,
                ) == name
        for command in group.commands.values():
            if hasattr(command, "commands"):
                visit(command)

    visit(root)


def test_retired_shellinit_spelling_is_not_routed() -> None:
    result = runner.invoke(app, ["shellinit"])

    assert result.exit_code == 2
    assert "No such command 'shellinit'" in result.stderr
