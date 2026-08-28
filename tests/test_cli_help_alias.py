"""Complete CLI-tree coverage for the shared Help option spellings."""

from __future__ import annotations

from collections.abc import Iterator

from typer.main import get_command
from typer.testing import CliRunner

from memcommit.adapters.console.entrypoint import app


def _registered_command_paths() -> Iterator[tuple[str, ...]]:
    root = get_command(app)
    root_context = root.make_context("mem", [], resilient_parsing=True)

    def visit(command, context, path: tuple[str, ...]) -> Iterator[tuple[str, ...]]:
        help_option = command.get_help_option(context)
        assert help_option is not None
        assert tuple(context.help_option_names) == ("-h", "--help")
        assert set(help_option.opts) == {"-h", "--help"}
        assert tuple(help_option.secondary_opts) == ()
        yield path

        if not (
            callable(getattr(command, "list_commands", None))
            and callable(getattr(command, "get_command", None))
        ):
            return
        for name in command.list_commands(context):
            child = command.get_command(context, name)
            if child is None:
                continue
            child_context = type(context)(child, info_name=name, parent=context)
            try:
                yield from visit(child, child_context, (*path, name))
            finally:
                child_context.close()

    try:
        yield from visit(root, root_context, ())
    finally:
        root_context.close()


def test_short_help_alias_covers_every_registered_command() -> None:
    runner = CliRunner()
    paths = tuple(_registered_command_paths())

    # Keep the complete tree—including the root, hidden aliases, and nested
    # developer routes—under one invariant as commands are added over time.
    assert paths
    for path in paths:
        result = runner.invoke(
            app,
            [*path, "-h"],
            env={"MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1"},
        )

        assert result.exit_code == 0, f"mem {' '.join(path)} -h\n{result.output}"
        assert "Usage:" in result.output
