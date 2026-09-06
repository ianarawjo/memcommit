"""Keep CLI and editable-command option spellings consistent and unambiguous."""

import click
import pytest
from typer.main import get_command

from memcommit.adapters.console.commands.meld import command_codec as meld
from memcommit.adapters.console.commands.update import command_codec as update


def test_context_memory_aliases_parse_identically_across_command_tree() -> None:
    from memcommit.adapters.console.entrypoint import app

    seen = set()

    def visit(command, path):
        with click.Context(command) as context:
            spellings = [
                spelling
                for parameter in command.params
                if isinstance(parameter, click.Option)
                for spelling in (*parameter.opts, *parameter.secondary_opts)
            ]
            for parameter in command.params:
                for long, short in (("--memory", "-m"), ("--context", "-c")):
                    if long not in parameter.opts:
                        continue
                    assert short in parameter.opts, (path, long)
                    assert spellings.count(short) == 1, (path, short)
                    parser = command.make_parser(context)
                    assert parser.parse_args([short, "sample"])[0] == (
                        parser.parse_args([long, "sample"])[0]
                    )
                    seen.add(long)
            if isinstance(command, click.Group):
                for name in command.list_commands(context):
                    child = command.get_command(context, name)
                    assert child is not None
                    visit(child, (*path, name))

    visit(get_command(app), ())
    assert seen == {"--memory", "--context"}


def test_log_manual_filter_does_not_compete_with_memory_alias() -> None:
    from memcommit.adapters.console.entrypoint import app

    command = get_command(app).commands["log"]
    with click.Context(command) as context:
        parser = command.make_parser(context)
        short = parser.parse_args(["-M"])[0]
        assert short == parser.parse_args(["--manual"])[0]
        assert short["manual"] is True
        assert parser.parse_args(["-m", "memory-uid"])[0]["memory"] == "memory-uid"
        with pytest.raises(click.BadOptionUsage):
            parser.parse_args(["-m"])


@pytest.mark.parametrize(
    "codec,operation,target",
    [(meld, "meld", "--into"), (update, "update", "--to")],
)
@pytest.mark.parametrize("text", ["exact Memory text", "-m", "--memory"])
def test_editable_memory_alias_preserves_literal_values(codec, operation, target, text):
    prefix = ["mem", operation]
    assert codec.parse_endpoint_argv([*prefix, "-m", text, target, "baseline"]) == (
        codec.parse_endpoint_argv([*prefix, "--memory", text, target, "baseline"])
    )


@pytest.mark.parametrize(
    "codec,operation,target",
    [(meld, "meld", "--into"), (update, "update", "--to")],
)
@pytest.mark.parametrize("first,second", [("-m", "--memory"), ("--memory", "-m")])
def test_editable_memory_alias_cannot_bypass_duplicate_check(
    codec, operation, target, first, second
):
    with pytest.raises(ValueError, match="requires exactly one value"):
        codec.parse_endpoint_argv(
            ["mem", operation, first, "one", second, "two", target, "baseline"]
        )
