import difflib
import re
from typing import Annotated

import typer
from rich.console import Console
from rich.text import Text

import memcommit.ops as ops
from memcommit.config import Config
from memcommit.context import AutoCheckpoint, Context
from memcommit.semantic.changes import AddChange, EditChange, ProposedChange, RemoveChange, apply_changes
from memcommit.semantic.llm import LLMClient, LLMError
from memcommit.store import MemoryStore


_DIFF_INDENT = "       "
_diff_console = Console(highlight=False)


def _word_tokens(text: str) -> list[str]:
    """Split text into alternating word / whitespace tokens, preserving all characters."""
    return re.findall(r"\S+|\s+", text)


def _word_diff_pair(old_line: str, new_line: str) -> tuple[Text, Text]:
    """
    Build Rich Text objects for one replaced line-pair.

    The base style of each Text is red / green so the whole line is coloured;
    words that actually changed are additionally bold so they pop out from the
    unchanged words on the same line.
    """
    old_toks = _word_tokens(old_line)
    new_toks = _word_tokens(new_line)

    old_out = Text(f"{_DIFF_INDENT}- ", style="red")
    new_out = Text(f"{_DIFF_INDENT}+ ", style="green")

    sm = difflib.SequenceMatcher(None, old_toks, new_toks, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        old_chunk = "".join(old_toks[i1:i2])
        new_chunk = "".join(new_toks[j1:j2])
        if tag == "equal":
            old_out.append(old_chunk)          # inherits red, not bold
            new_out.append(new_chunk)          # inherits green, not bold
        else:                                  # replace / delete / insert
            if old_chunk:
                old_out.append(old_chunk, style="bold")   # bold red
            if new_chunk:
                new_out.append(new_chunk, style="bold")   # bold green

    return old_out, new_out


def _print_edit_diff(old: str, new: str) -> None:
    """
    Print a word-level diff of old vs new using Rich, indented under the EDIT header.

    Changed lines show a -/+ pair with the specific changed words in bold.
    Unchanged lines are shown dimmed for context (full content, never truncated).
    """
    old_lines = old.splitlines() or [""]
    new_lines = new.splitlines() or [""]

    sm = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    had_output = False

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for line in old_lines[i1:i2]:
                _diff_console.print(Text(f"{_DIFF_INDENT}  {line}", style="dim"))
                had_output = True
        elif tag == "replace":
            old_chunk = old_lines[i1:i2]
            new_chunk = new_lines[j1:j2]
            pairs = min(len(old_chunk), len(new_chunk))
            for k in range(pairs):
                old_t, new_t = _word_diff_pair(old_chunk[k], new_chunk[k])
                _diff_console.print(old_t)
                _diff_console.print(new_t)
            for line in old_chunk[pairs:]:     # unpaired surplus old lines
                _diff_console.print(Text(f"{_DIFF_INDENT}- {line}", style="red"))
            for line in new_chunk[pairs:]:     # unpaired surplus new lines
                _diff_console.print(Text(f"{_DIFF_INDENT}+ {line}", style="green"))
            had_output = True
        elif tag == "delete":
            for line in old_lines[i1:i2]:
                _diff_console.print(Text(f"{_DIFF_INDENT}- {line}", style="red"))
                had_output = True
        elif tag == "insert":
            for line in new_lines[j1:j2]:
                _diff_console.print(Text(f"{_DIFF_INDENT}+ {line}", style="green"))
                had_output = True

    if not had_output:
        typer.secho(f"{_DIFF_INDENT}(no textual difference)", dim=True)


def _print_proposals(proposals: list[ProposedChange], new_info: str) -> None:
    typer.echo()
    typer.secho(f'Proposed changes to integrate: "{new_info[:60]}"', bold=True)
    typer.echo("─" * 56)

    if not proposals:
        typer.secho(
            "  (no changes proposed — information already captured in context)",
            dim=True,
        )
        typer.echo("─" * 56)
        return

    for i, change in enumerate(proposals, 1):
        if isinstance(change, AddChange):
            preview = change.content[:60]
            ellipsis = "…" if len(change.content) > 60 else ""
            typer.secho(
                f'  {i}  ADD     "{preview}{ellipsis}"',
                fg=typer.colors.GREEN, bold=True,
            )
            typer.secho(f"       Reason: {change.reason}", dim=True)
        elif isinstance(change, RemoveChange):
            preview = change.content[:60]
            ellipsis = "…" if len(change.content) > 60 else ""
            typer.secho(
                f'  {i}  REMOVE  [{change.uid[:8]}]  "{preview}{ellipsis}"',
                fg=typer.colors.RED, bold=True,
            )
            typer.secho(f"       Reason: {change.reason}", dim=True)
        elif isinstance(change, EditChange):
            typer.secho(
                f"  {i}  EDIT    [{change.uid[:8]}]",
                fg=typer.colors.YELLOW, bold=True,
            )
            _print_edit_diff(change.old_content, change.new_content)
            typer.secho(f"       Reason: {change.reason}", dim=True)
        typer.echo()

    typer.echo("─" * 56)


def _run_interactive_integrate(
    ctx: Context,
    new_info: str,
    llm: LLMClient,
) -> list[ProposedChange]:
    typer.secho(f"Consulting {llm.model!r}...", dim=True)
    proposals, batch_histories = ops.integrate(ctx, new_info, llm)

    while True:
        _print_proposals(proposals, new_info)

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
            adds    = sum(1 for c in proposals if isinstance(c, AddChange))
            removes = sum(1 for c in proposals if isinstance(c, RemoveChange))
            edits   = sum(1 for c in proposals if isinstance(c, EditChange))
            parts = (
                ([f"{adds} added"]        if adds    else [])
                + ([f"{removes} removed"] if removes else [])
                + ([f"{edits} edited"]    if edits   else [])
            )
            typer.secho(f"Done: {', '.join(parts)}.", fg=typer.colors.GREEN)
            return proposals

        if decision.lower() in ("n", "no"):
            typer.echo("Aborted — no changes made.")
            return []

        feedback = decision if not decision.lower().startswith("r") else ""
        if not feedback:
            feedback = typer.prompt(
                "Describe what to change", default="", show_default=False
            ).strip()
        if not feedback:
            continue

        typer.secho(f"Revising with {llm.model!r}...", dim=True)
        proposals, batch_histories = ops.revise_integrate(
            feedback, llm, batch_histories, ctx, new_info
        )


def cmd(
    info: Annotated[
        str,
        typer.Argument(
            help="Information to intelligently integrate into the current context"
        ),
    ],
) -> None:
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
        applied = _run_interactive_integrate(ctx, info, LLMClient(model=model))
    except (LLMError, ValueError) as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if applied:
        adds    = [c for c in applied if isinstance(c, AddChange)]
        removes = [c for c in applied if isinstance(c, RemoveChange)]
        edits   = [c for c in applied if isinstance(c, EditChange)]
        parts = []
        if adds:
            parts.append(
                f'added "{adds[0].content[:40]}"'
                if len(adds) == 1 else f"added {len(adds)}"
            )
        if removes:
            parts.append(
                f'removed "{removes[0].content[:40]}"'
                if len(removes) == 1 else f"removed {len(removes)}"
            )
        if edits:
            parts.append(
                f"edited [{edits[0].uid[:8]}]"
                if len(edits) == 1 else f"edited {len(edits)}"
            )
        store.save(ctx, AutoCheckpoint(
            command="integrate",
            args={"info": info},
            description=f'Integrated ({info[:40]}): {", ".join(parts)}',
        ))
