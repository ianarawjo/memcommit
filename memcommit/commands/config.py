"""mem config — read and write global configuration."""
import typer

from memcommit.config import Config

app = typer.Typer(help="Read and write global mem configuration.")


@app.command("set")
def config_set(
    key: str = typer.Argument(help="Config key  (e.g. 'llm')"),
    value: str = typer.Argument(help="Value to set"),
) -> None:
    """Set a configuration value.

    \b
    Keys:
      llm   — Ollama model name for semantic operations (e.g. llama3.2, mistral)
    """
    # Normalise: "llm" is shorthand for "llm_model"
    if key == "llm":
        key = "llm_model"
    Config().set(key, value)
    typer.secho(f"Set {key} = {value!r}", fg=typer.colors.GREEN)


@app.command("show")
def config_show() -> None:
    """Show all current configuration values."""
    data = Config().all()
    if not data:
        typer.echo("(no configuration set)")
        return
    for k, v in data.items():
        typer.echo(f"  {k} = {v!r}")
