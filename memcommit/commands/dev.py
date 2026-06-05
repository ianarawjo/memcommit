"""mem dev — developer tools for evaluation and testing (hidden from main help)."""
from typing import Annotated, Optional

import json
import typer

app = typer.Typer(help="Developer tools: evals, diagnostics.")

_SUPPORTED_COMMANDS = ("forget",)

_FAKE_SYSTEM_PROMPT = """\
You are a test-data generator for a memory store.
Given a theme, produce a JSON object with a single key "memories" whose value is an array of
20–30 short, realistic, self-contained sentences that could plausibly be stored as individual
memories on that theme. Each sentence should be distinct and specific. Try to generate 
a diverse set of facts, opinions, and experiences related to the theme. Avoid generic or vague statements.
Return ONLY valid JSON — no markdown, no commentary."""


@app.command("fake")
def dev_fake(
    context_name: Annotated[str, typer.Argument(help="Name for the new context to create")],
    prompt: Annotated[str, typer.Argument(help="Theme / description to steer the generated memories")],
) -> None:
    """
    Create a new context and populate it with LLM-generated fake memories.

    Uses the configured LLM (mem config set llm <model>) to produce a batch of
    realistic-looking memory items steered by PROMPT. Useful for quick testing
    without manually entering data.

    \b
    Example:
        mem dev fake test-user "a software engineer who likes hiking and coffee"
    """
    from memcommit.config import Config
    from memcommit.context import Context
    from memcommit.semantic.llm import LLMClient, LLMError
    from memcommit.store import MemoryStore
    import memcommit.ops as ops

    config = Config()
    try:
        model = config.require_llm_model()
    except RuntimeError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    store = MemoryStore()
    if store.context_exists(context_name):
        typer.secho(
            f"Error: context '{context_name}' already exists.",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(1)

    typer.secho(f"Asking {model!r} for fake memories about: {prompt!r} …", dim=True)

    llm = LLMClient(model=model)
    try:
        raw = llm.chat([
            {"role": "system", "content": _FAKE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ])
    except LLMError as e:
        typer.secho(f"LLM error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        data = json.loads(raw)
        items: list[str] = data["memories"]
        if not isinstance(items, list):
            raise ValueError("'memories' is not a list")
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        typer.secho(f"Could not parse LLM response: {e}\nRaw output:\n{raw}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    ctx = ops.init(context_name)
    for item in items:
        if isinstance(item, str) and item.strip():
            ctx.add(item.strip())

    store.save(ctx)
    store.set_current(context_name)
    typer.echo("Generated memories:")
    for idx, info in enumerate(ctx.get_all().values(), start=1):
        content = getattr(info, "content", str(info))
        typer.echo(f"{idx:>2}. {content}")
    typer.secho(
        f"Created context '{context_name}' with {len(ctx.get_all())} fake memories.",
        fg=typer.colors.GREEN,
    )


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

    from memcommit.semantic.llm import LLMError
    from memcommit.eval.runner import run_forget_eval

    try:
        if command == "forget":
            run_forget_eval(llm_model=llm, runs=runs, print_fn=typer.echo)
    except LLMError as e:
        typer.secho(f"LLM error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
