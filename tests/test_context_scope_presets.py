"""Contracts for the shared CLI/TUI Context-scope presets."""

import pytest
from click import Group, Option
from typer.main import get_command
from typer.testing import CliRunner

import memcommit.ops as ops
import memcommit.commands.query as query_command
from memcommit.cli import app
from memcommit.context_targeting.presets import (
    ContextScopePreset,
    ContextTraversal,
    resolve_context_traversal,
    resolve_descendant_scopes,
    resolve_scope_preset,
)
from memcommit.store import MemoryStore


runner = CliRunner()


def test_scope_preset_defaults_to_direct_and_accepts_recursive():
    assert resolve_scope_preset(direct=False, recursive=False) is (
        ContextScopePreset.DIRECT
    )
    assert resolve_scope_preset(direct=False, recursive=True) is (
        ContextScopePreset.RECURSIVE
    )


def test_scope_preset_rejects_both_common_flags():
    with pytest.raises(ValueError, match="either --direct/-d or --recursive/-r"):
        resolve_scope_preset(direct=True, recursive=True)


def test_role_specific_descendant_flags_override_the_common_preset():
    assert resolve_descendant_scopes(
        preset=ContextScopePreset.RECURSIVE,
        explicit=(None, False),
    ) == (True, False)
    assert resolve_descendant_scopes(
        preset=ContextScopePreset.DIRECT,
        explicit=(True, None),
    ) == (True, False)


def test_independent_lexical_and_embedded_axes_refine_the_preset():
    traversal = resolve_context_traversal(
        preset=ContextScopePreset.RECURSIVE,
        follow_embeds=False,
    )
    assert traversal.include_descendants is True
    assert traversal.follow_embeds is False

    traversal = resolve_context_traversal(
        preset=ContextScopePreset.DIRECT,
        include_descendants=True,
    )
    assert traversal.include_descendants is True
    assert traversal.follow_embeds is False


def _command(path: tuple[str, ...]):
    command = get_command(app)
    for name in path:
        assert isinstance(command, Group)
        command = command.commands[name]
    return command


@pytest.mark.parametrize(
    "path",
    (
        ("branch",),
        ("checkout",),
        ("compare",),
        ("find",),
        ("impact",),
        ("import",),
        ("list",),
        ("lock",),
        ("lock", "context"),
        ("ls",),
        ("meld",),
        ("profile", "grant", "create"),
        ("profile", "grant", "update"),
        ("query",),
        ("sever",),
        ("summarize",),
        ("unlock",),
        ("unlock", "context"),
        ("update",),
    ),
)
def test_context_scope_commands_expose_both_common_short_flags(path):
    options = tuple(
        parameter
        for parameter in _command(path).params
        if isinstance(parameter, Option)
    )
    spellings = {
        spelling
        for option in options
        for spelling in (*option.opts, *option.secondary_opts)
    }
    assert "-d" in spellings, path
    assert "-r" in spellings, path


@pytest.mark.parametrize(
    "path",
    (
        ("atomize",),
        ("find-ambiguities",),
        ("find-conflicts",),
        ("find-duplicates",),
        ("forget",),
    ),
)
def test_intentionally_direct_only_operations_do_not_advertise_recursive(path):
    options = tuple(
        parameter
        for parameter in _command(path).params
        if isinstance(parameter, Option)
    )
    spellings = {
        spelling
        for option in options
        for spelling in (*option.opts, *option.secondary_opts)
    }
    assert "-r" not in spellings


def test_query_common_presets_reach_the_typed_ordinary_request(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context = ops.init("query-scope")
    store.save(context)
    store.set_current(context.name)
    observed = []
    monkeypatch.setattr(
        query_command,
        "_query_ordinary_context",
        lambda _store, **kwargs: observed.append(kwargs["traversal"]),
    )

    direct = runner.invoke(app, ["query", "What is recorded?"])
    recursive = runner.invoke(app, ["query", "-r", "What is recorded?"])

    assert direct.exit_code == 0, direct.output
    assert recursive.exit_code == 0, recursive.output
    assert observed == [
        ContextTraversal(include_descendants=False, follow_embeds=False),
        ContextTraversal(include_descendants=True, follow_embeds=True),
    ]
