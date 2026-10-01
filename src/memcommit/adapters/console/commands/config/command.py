"""mem config — read and write global configuration."""

import typer

from memcommit.adapters.console.coordination.command_group import CanonicalCommandGroup
from memcommit.application.operations.config import (
    list_configuration,
    set_configuration,
)
from memcommit.configuration.config import Config
from memcommit.adapters.console.commands.config.operation_contexts import (
    operation_contexts,
)

app = typer.Typer(
    cls=CanonicalCommandGroup,
    invoke_without_command=True,
    no_args_is_help=False,
    help="Read and write global mem configuration.",
)


@app.command("operation-contexts")
def config_operation_contexts() -> None:
    """Browse Contexts packaged with operations."""
    operation_contexts()


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
      workspace_dir — workspace containing .mem/ and contexts/
      llm       — legacy Ollama model name
      provider  — codex_chatgpt, ollama, or openrouter
      model     — model name used by the selected provider
    """
    try:
        entry = set_configuration(Config(), key, value)
    except (OSError, ValueError) as error:
        from memcommit.adapters.console.terminal.core.output import echo_text

        echo_text("Config error: {error}", error=error, err=True)
        raise typer.Exit(1) from error
    if key == "workspace_dir":
        from memcommit.adapters.console.terminal.core.output import echo_text

        echo_text("Workspace: {path}", path=entry.value)
        typer.echo("Internal data: .mem/ · File workspace: contexts/")
        typer.echo(
            "Previous data was retained. Automatic file synchronization is not enabled."
        )
        return
    typer.secho(
        f"Set {entry.key} = {entry.value!r}",
        fg=typer.colors.GREEN,
    )


@app.command("show")
def config_show() -> None:
    """Show all current configuration values."""
    _render_config()
