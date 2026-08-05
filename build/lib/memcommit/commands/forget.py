from typing import Annotated

import typer

import memcommit.ops as ops
from memcommit.config import Config
from memcommit.context import AutoCheckpoint, Context
from memcommit.semantic.llm import LLMClient, LLMError
from memcommit.semantic.changes import EditChange, RemoveChange, ProposedChange, apply_changes
from memcommit.store import MemoryStore


def _print_proposals(proposals: list[ProposedChange], query: str) -> None:
    typer.echo()
    typer.secho(f'Proposed changes for "{query}"', bold=True)
    typer.echo("-" * 56)
    if not proposals:
        typer.secho("  (no changes proposed - nothing matched)", dim=True)
        typer.echo("-" * 56)
        return

    for i, change in enumerate(proposals, 1):
        if isinstance(change, RemoveChange):
            typer.secho(f'  {i}  REMOVE  [{change.uid[:8]}]  "{change.content}"', fg=typer.colors.RED, bold=True)
            typer.secho(f"       Reason: {change.reason}", dim=True)
        elif isinstance(change, EditChange):
            typer.secho(f'  {i}  EDIT    [{change.uid[:8]}]  "{change.old_content}"', fg=typer.colors.YELLOW, bold=True)
            typer.secho(f'         -> "{change.new_content}"', fg=typer.colors.GREEN)
            typer.secho(f"       Reason: {change.reason}", dim=True)
        typer.echo()

    typer.echo("-" * 56)


def _run_interactive_forget(
    ctx: Context,
    info: str,
    llm: LLMClient,
) -> list[ProposedChange]:
    typer.secho(f"Consulting {llm.model!r}...", dim=True)
    proposals, history = ops.forget(ctx, info, llm)

    while True:
        _print_proposals(proposals, info)

        if not proposals:
            typer.echo("Nothing to apply.")
            return []

        n = len(proposals)
        label = "change" if n == 1 else "changes"
        typer.echo(f"Apply {'this' if n == 1 else 'these'} {n} {label}?")
        typer.secho("  y = apply    n = abort    r = revise with feedback", dim=True)
        decision = typer.prompt(">", default="", show_default=False).strip()

        if decision.lower() in ("y", "yes"):
            apply_changes(ctx, proposals)
            removes = sum(1 for c in proposals if isinstance(c, RemoveChange))
            edits = sum(1 for c in proposals if isinstance(c, EditChange))
            parts = (
                ([f"{removes} removed"] if removes else [])
                + ([f"{edits} edited"] if edits else [])
            )
            typer.secho(f"Done: {', '.join(parts)}.", fg=typer.colors.GREEN)
            return proposals

        if decision.lower() in ("n", "no"):
            typer.echo("Aborted - no changes made.")
            return []

        feedback = decision if not decision.lower().startswith("r") else ""
        if not feedback:
            feedback = typer.prompt("Describe what to change", default="", show_default=False).strip()
        if not feedback:
            continue

        typer.secho(f"Revising with {llm.model!r}...", dim=True)
        proposals, history = ops.revise_forget(feedback, llm, history, ctx)


def cmd(info: Annotated[str, typer.Argument(help="Description of memories to forget")]) -> None:
    config = Config()
    try:
        model = config.require_llm_model()
    except RuntimeError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    store = MemoryStore()
    try:
        ctx = store.load_current_direct()
    except RuntimeError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        applied = _run_interactive_forget(ctx, info, LLMClient(model=model))
    except (LLMError, ValueError) as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if applied:
        removes = [c for c in applied if isinstance(c, RemoveChange)]
        edits = [c for c in applied if isinstance(c, EditChange)]
        parts = []
        if removes:
            parts.append(f'removed "{removes[0].content[:40]}"' if len(removes) == 1 else f"removed {len(removes)}")
        if edits:
            parts.append(f'edited "{edits[0].old_content[:40]}"' if len(edits) == 1 else f"edited {len(edits)}")
        store.save(ctx, AutoCheckpoint(
            command="forget",
            args={"query": info},
            description=f'Forgot ({info[:40]}): {", ".join(parts)}',
        ))
