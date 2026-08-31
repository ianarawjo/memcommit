"""mem config — read and write global configuration."""

import typer

from memcommit.adapters.console.coordination.command_group import CanonicalCommandGroup
from memcommit.application.operations.config import (
    list_configuration,
    set_configuration,
)
from memcommit.configuration.config import Config

app = typer.Typer(
    cls=CanonicalCommandGroup,
    invoke_without_command=True,
    no_args_is_help=False,
    help="Read and write global mem configuration.",
)


def _render_config() -> None:
    entries = list_configuration(Config())
    if not entries:
        typer.echo("(no configuration set)")
        return
    for entry in entries:
        typer.echo(f"  {entry.key} = {entry.value!r}")


@app.callback(invoke_without_command=True)
def config_group(ctx: typer.Context) -> None:
    """Show current values when no explicit configuration action is selected."""
    if ctx.invoked_subcommand is None:
        _render_config()


@app.command("set")
def config_set(
    key: str = typer.Argument(help="Config key  (e.g. 'llm')"),
    value: str = typer.Argument(help="Value to set"),
) -> None:
    """Set a configuration value.

    \b
    Keys:
      llm       — legacy Ollama model name
      provider  — codex_chatgpt, ollama, or openrouter
      model     — model name used by the selected provider
    """
    entry = set_configuration(Config(), key, value)
    typer.secho(
        f"Set {entry.key} = {entry.value!r}",
        fg=typer.colors.GREEN,
    )


@app.command("show")
def config_show() -> None:
    """Show all current configuration values."""
    _render_config()
