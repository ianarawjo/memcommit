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
from memcommit.operations.query.ordinary_application import OrdinaryQueryResponse
from memcommit.profiles import ProfileError
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


def _command_options(path: tuple[str, ...]) -> tuple[Option, ...]:
    return tuple(
        parameter
        for parameter in _command(path).params
        if isinstance(parameter, Option)
    )


def _walk_commands(command, path: tuple[str, ...] = ()):
    yield path, command
    if isinstance(command, Group):
        for name, child in command.commands.items():
            yield from _walk_commands(child, (*path, name))


@pytest.mark.parametrize(
    "path",
    (
        ("branch",),
        ("checkout",),
        ("compare",),
        ("dedup",),
        ("dedun",),
        ("distill",),
        ("find",),
        ("find-duplicates",),
        ("find-redundancies",),
        ("impact",),
        ("impact", "distill"),
        ("import",),
        ("list",),
        ("lock",),
        ("lock", "context"),
        ("ls",),
        ("meld",),
        ("merge",),
        ("profile", "grant", "create"),
        ("profile", "grant", "update"),
        ("query",),
        ("replace",),
        ("search",),
        ("sever",),
        ("status",),
        ("summarize",),
        ("unlock",),
        ("unlock", "context"),
        ("update",),
    ),
)
def test_context_scope_commands_expose_both_common_short_flags(path):
    options = _command_options(path)
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
        ("forget",),
    ),
)
def test_intentionally_direct_only_operations_do_not_advertise_recursive(path):
    options = _command_options(path)
    spellings = {
        spelling
        for option in options
        for spelling in (*option.opts, *option.secondary_opts)
    }
    assert "-r" not in spellings


def test_r_short_alias_is_reserved_for_recursive_scope() -> None:
    for path, command in _walk_commands(get_command(app)):
        for option in (
            parameter
            for parameter in command.params
            if isinstance(parameter, Option)
            and "-r" in (*parameter.opts, *parameter.secondary_opts)
        ):
            assert option.name in {"recursive", "refresh_scope"}, (
                path,
                option.name,
            )

    elaborate_options = _command_options(("elaborate",))
    rule = next(option for option in elaborate_options if option.name == "rule")
    assert rule.opts == ["--rule"]


@pytest.mark.parametrize(
    ("path", "roles"),
    (
        (("branch",), ("source",)),
        (("compare",), ("reference", "compared")),
        (("impact",), ("source", "target")),
        (("meld",), ("left", "right")),
        (("sever",), ("source", "criteria")),
        (("update",), ("source", "target")),
    ),
)
def test_role_scope_flags_share_canonical_and_compatibility_spelling(
    path: tuple[str, ...],
    roles: tuple[str, ...],
) -> None:
    command = _command(path)
    options = _command_options(path)
    for role in roles:
        descendants = f"--{role}-descendants"
        option = next(item for item in options if descendants in item.opts)
        assert option.opts == [descendants]
        assert option.secondary_opts == [
            f"--{role}-root-only",
            f"--{role}-only",
        ]
        for spelling, expected in (
            (descendants, True),
            (f"--{role}-root-only", False),
            (f"--{role}-only", False),
        ):
            context = command.make_context(
                path[-1],
                [spelling],
                resilient_parsing=True,
            )
            assert context.params[f"{role}_descendants"] is expected


@pytest.mark.parametrize(
    ("path", "roles", "root_only_role"),
    (
        (("compare",), ("reference", "compared"), "compared"),
        (("impact",), ("source", "target"), "target"),
        (("meld",), ("left", "right"), "right"),
        (("sever",), ("source", "criteria"), "criteria"),
        (("update",), ("source", "target"), "target"),
    ),
)
def test_recursive_preset_and_one_role_override_are_order_independent(
    path: tuple[str, ...],
    roles: tuple[str, str],
    root_only_role: str,
) -> None:
    command = _command(path)
    root_only = f"--{root_only_role}-root-only"

    for argv in (("-r", root_only), (root_only, "-r")):
        context = command.make_context(
            path[-1],
            list(argv),
            resilient_parsing=True,
        )
        preset = resolve_scope_preset(
            direct=context.params["direct"],
            recursive=context.params["recursive"],
        )
        resolved = resolve_descendant_scopes(
            preset=preset,
            explicit=tuple(
                context.params[f"{role}_descendants"] for role in roles
            ),
        )

        assert resolved == tuple(role != root_only_role for role in roles)


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


def test_query_all_and_short_alias_freeze_every_readable_context(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    first = ops.init("query/first")
    second = ops.init("query/second")
    for context in (first, second):
        store.save(context)
    store.set_current(first.name)
    observed = []
    authorized = []

    def execute(request, *, catalog, **_kwargs):
        observed.append((request, tuple(catalog.list_context_names())))
        return OrdinaryQueryResponse(
            request,
            "SUMMARY\n  (no grounded answer found)",
            False,
        )

    monkeypatch.setattr(query_command, "execute_ordinary_query", execute)
    monkeypatch.setattr(query_command, "render_ordinary_query_response", lambda _r: None)
    monkeypatch.setattr(
        query_command,
        "authorize_combination",
        lambda accesses: authorized.append(
            tuple(access.display_name for access in accesses)
        ),
    )

    for option in ("--all", "-a"):
        result = runner.invoke(app, ["query", option, "What is recorded?"])
        assert result.exit_code == 0, result.output

    expected_names = (first.name, second.name)
    assert [entry[0].target_names for entry in observed] == [
        expected_names,
        expected_names,
    ]
    assert [entry[1] for entry in observed] == [expected_names, expected_names]
    assert authorized == [expected_names, expected_names]


def test_query_all_rejects_explicit_context_and_query_only_form(
    isolated_store,
):
    store = MemoryStore()
    context = ops.init("query/source")
    store.save(context)
    store.set_current(context.name)

    explicit = runner.invoke(
        app,
        ["query", "--all", "--context", context.name, "What is recorded?"],
    )
    query_only = runner.invoke(
        app,
        ["query", "--all", "public/view", "What is recorded?"],
    )

    assert explicit.exit_code == 2
    assert "--all/-a cannot be combined with --context/-c" in explicit.output
    assert query_only.exit_code == 2
    assert "ordinary one-question form" in query_only.output


def test_query_all_authority_failure_precedes_provider_execution(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context = ops.init("query/source")
    store.save(context)
    store.set_current(context.name)
    monkeypatch.setattr(
        query_command,
        "authorize_combination",
        lambda _accesses: (_ for _ in ()).throw(ProfileError("combine denied")),
    )
    monkeypatch.setattr(
        query_command,
        "execute_ordinary_query",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("provider execution must remain disconnected")
        ),
    )

    result = runner.invoke(app, ["query", "--all", "What is recorded?"])

    assert result.exit_code == 1
    assert "combine denied" in result.output
