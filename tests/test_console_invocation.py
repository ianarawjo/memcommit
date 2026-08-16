"""Console routing contracts for bare TUI and explicit plain invocations."""

from typing import Annotated, Optional

import typer
from typer.testing import CliRunner

from memcommit.console_invocation import (
    ConsoleRoute,
    InvocationShape,
    TerminalCapabilities,
    classify_click_invocation,
    select_console_route,
)


runner = CliRunner()


def _shape_app():
    app = typer.Typer()

    @app.command()
    def inspect(
        operand: Annotated[Optional[str], typer.Argument()] = None,
        limit: Annotated[int, typer.Option("--limit")] = 5,
        descendants: Annotated[
            Optional[bool],
            typer.Option("--descendants/--context-only"),
        ] = None,
    ) -> None:
        typer.echo(classify_click_invocation().value)

    return app


def test_bare_command_has_no_commandline_parameter_source():
    result = runner.invoke(_shape_app(), [])

    assert result.exit_code == 0
    assert result.stdout.strip() == "BARE"


def test_positional_operand_makes_invocation_explicit():
    result = runner.invoke(_shape_app(), ["question"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "EXPLICIT"


def test_explicit_default_value_still_makes_invocation_explicit():
    result = runner.invoke(_shape_app(), ["--limit", "5"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "EXPLICIT"


def test_explicit_negative_boolean_makes_invocation_explicit():
    result = runner.invoke(_shape_app(), ["--context-only"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "EXPLICIT"


def test_only_bare_tui_capable_interactive_invocation_routes_to_tui():
    terminal = TerminalCapabilities(stdin_is_tty=True, stdout_is_tty=True)

    assert select_console_route(
        InvocationShape.BARE,
        terminal=terminal,
        supports_tui=True,
    ) is ConsoleRoute.TUI
    assert select_console_route(
        InvocationShape.EXPLICIT,
        terminal=terminal,
        supports_tui=True,
    ) is ConsoleRoute.PLAIN
    assert select_console_route(
        InvocationShape.BARE,
        terminal=terminal,
        supports_tui=False,
    ) is ConsoleRoute.PLAIN


def test_bare_noninteractive_invocation_routes_to_plain():
    assert select_console_route(
        InvocationShape.BARE,
        terminal=TerminalCapabilities(
            stdin_is_tty=False,
            stdout_is_tty=True,
        ),
        supports_tui=True,
    ) is ConsoleRoute.PLAIN
