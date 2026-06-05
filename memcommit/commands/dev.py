"""mem dev — developer tools for evaluation and testing (hidden from main help)."""
from typing import Annotated, Optional

import typer

app = typer.Typer(help="Developer tools: evals, diagnostics.")

_SUPPORTED_COMMANDS = ("forget",)


@app.command("eval")
def dev_eval(
    command: Annotated[str, typer.Option("--command", "-c", help=f"Semantic command to evaluate: {_SUPPORTED_COMMANDS}")],
    llm: Annotated[str, typer.Option("--llm", "-m", help="Ollama model name (e.g. llama3.2)")],
    runs: Annotated[int, typer.Option("--runs", "-n", help="Number of runs per test case")] = 3,
) -> None:
    """
    Run an evaluation suite for a semantic operation against a given LLM model.

    Reports per-case precision, recall, and stability (consistency across runs).
    Useful for vetting a new model before using it as a semantic backend.

    \b
    Example:
        mem dev eval --command forget --llm llama3.2 --runs 3
    """
    if command not in _SUPPORTED_COMMANDS:
        typer.secho(
            f"Error: unsupported command '{command}'. Choose from: {', '.join(_SUPPORTED_COMMANDS)}",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(1)

    from memcommit.llm import LLMError
    from memcommit.eval.runner import run_forget_eval

    try:
        if command == "forget":
            run_forget_eval(llm_model=llm, runs=runs, print_fn=typer.echo)
    except LLMError as e:
        typer.secho(f"LLM error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
