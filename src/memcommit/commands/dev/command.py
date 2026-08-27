"""mem dev — developer tools for evaluation and testing (hidden from main help)."""
import copy
from pathlib import Path
from typing import Annotated

import json
import typer

from memcommit.adapters.interfaces.cli.command_group import CanonicalCommandGroup
from memcommit.context_locator import resolve_context_locator

app = typer.Typer(
    cls=CanonicalCommandGroup,
    help="Developer tools: evals, diagnostics.",
)
query_source_app = typer.Typer(
    cls=CanonicalCommandGroup,
    help="Install concealed sources for the query-only research prototype."
)
app.add_typer(query_source_app, name="query-source")

_SUPPORTED_COMMANDS = ("forget", "integrate")

_FAKE_SYSTEM_PROMPT = """\
You are a test-data generator for a memory store.
Given a theme, produce a JSON object with a single key "memories" whose value is an array of
20–30 short, realistic, self-contained sentences that could plausibly be stored as individual
memories on that theme. Each sentence should be distinct and specific. Try to generate 
a diverse set of facts, opinions, and experiences related to the theme. Avoid generic or vague statements.
Return ONLY valid JSON — no markdown, no commentary."""


@query_source_app.command("install")
def dev_query_source_install(
    name: Annotated[
        str,
        typer.Argument(help="Name shown for the query-only Context"),
    ],
    source_file: Annotated[
        Path,
        typer.Option(
            "--from",
            help="UTF-8 text or Markdown file containing the concealed source",
        ),
    ],
    into: Annotated[
        str,
        typer.Option("--into", help="Context that will receive the query reference"),
    ],
) -> None:
    """
    Install one local query-only source for a study fixture.

    This hidden command simulates query-only access. The source remains
    readable to the local OS user and is not a production security boundary.
    """
    import memcommit.application.ops as ops
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore()
    try:
        current_name = store.current_context_name()
        target_name = resolve_context_locator(into, current=current_name)
        parent = store.load_direct(target_name)
    except (FileNotFoundError, OSError, ValueError) as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    original_parent = copy.deepcopy(parent)

    try:
        content = source_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as e:
        typer.secho(
            f"Error: could not read UTF-8 source file: {e}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    source = None
    parent_saved = False
    saved_parent_digest = None
    try:
        source = store.create_query_source(name, content)
        ref = ops.reference_query_context(name, source.uid, parent)
        store.save(parent)
        parent_saved = True
        saved_parent_digest = parent._store_digest
        store.checkpoint(
            parent,
            message=f"Installed query-only Context '{name}' in '{target_name}'",
            command="dev query-source install",
            args={
                "name": name,
                "into": target_name,
                "provider": ref.provider,
            },
            description=(
                f"Installed query-only Context '{name}' in '{target_name}'"
            ),
            auto=True,
        )
    except (OSError, RuntimeError, ValueError) as e:
        rollback_error = None
        if parent_saved:
            try:
                # Restore only the exact version this operation just saved.
                # The explicit post-save digest preserves rollback without
                # allowing a concurrent writer to be overwritten.
                store.save(
                    original_parent,
                    expected_context_digest=saved_parent_digest,
                )
            except (OSError, RuntimeError, ValueError) as restore_error:
                rollback_error = restore_error
        if source is not None and rollback_error is None:
            try:
                store.delete_query_source(source.uid)
            except (FileNotFoundError, OSError, ValueError) as delete_error:
                rollback_error = delete_error
        detail = (
            f"{e}; rollback also failed: {rollback_error}"
            if rollback_error is not None
            else str(e)
        )
        typer.secho(f"Error: {detail}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    typer.secho(
        f"Installed query-only Context '{name}' in '{target_name}'.",
        fg=typer.colors.GREEN,
    )


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
    from memcommit.configuration.config import Config
    from memcommit.semantic.llm import LLMClient, LLMError
    from memcommit.persistence.store import MemoryStore
    import memcommit.application.ops as ops

    config = Config()
    try:
        model = config.require_llm_model()
    except RuntimeError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    store = MemoryStore()
    try:
        expected_current = store.current_context_name()
        store.assert_context_creatable(context_name)
    except FileExistsError:
        typer.secho(
            f"Error: context '{context_name}' already exists.",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(1)
    except (OSError, ValueError) as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
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

    try:
        store.create_context(ctx)
    except (OSError, RuntimeError, ValueError) as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    try:
        store.set_current_context_if(
            expected_current,
            context_name,
            expected_context_uid=ctx.uid,
            expected_context_digest=ctx._store_digest or "",
        )
    except (OSError, RuntimeError, ValueError) as e:
        typer.secho(
            f"Error: created context '{context_name}', but could not switch "
            f"to it ({e}). The new Context was preserved.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
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
    command: Annotated[str, typer.Option("--command", "-c", help=f"Semantic benchmark to evaluate: {_SUPPORTED_COMMANDS}")],
    llm: Annotated[str, typer.Option("--llm", "-m", help="Ollama model name (e.g. llama3.2)")],
    runs: Annotated[int, typer.Option("--runs", "-n", help="Number of runs per test case")] = 3,
) -> None:
    """
    Run a frozen semantic benchmark against a given LLM model.

    Reports per-case precision, recall, and stability (consistency across runs).
    Useful for vetting a new model before using it as a semantic backend. A
    benchmark name may identify a retired public command.

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
    from memcommit.application.evaluation.runner import run_forget_eval, run_integrate_eval

    try:
        if command == "forget":
            run_forget_eval(llm_model=llm, runs=runs, print_fn=typer.echo)
        elif command == "integrate":
            run_integrate_eval(llm_model=llm, runs=runs, print_fn=typer.echo)
    except LLMError as e:
        typer.secho(f"LLM error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
