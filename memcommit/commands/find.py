import subprocess
import shlex
import sys
from dataclasses import dataclass, replace
from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.exact_command_review import (
    ExactCommandReview,
    format_exact_command,
)
from memcommit.commands.find_chat_shell import (
    FindChatMessage,
    FindChatResult,
    FindChatSessionResult,
    FindChatState,
    run_find_chat_session,
)
from memcommit.context import Memory, MemoryRef, QueryContextRef
from memcommit.find_turn_dialogue import (
    FindTurnAction,
    FindTurnAsk,
    interpret_find_turn,
)
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.search import FindError, SearchMatch
from memcommit.store import MemoryStore


@dataclass(frozen=True)
class FindShowProposal:
    """One locally resolved read-only command for a visible Find result."""

    action: FindTurnAction
    result: FindChatResult
    review: ExactCommandReview
    submitted_text: str


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _render_labeled_content(label: str, content: str) -> None:
    """Render the first content line beside its item and align continuations."""
    lines = content.splitlines() or [""]
    typer.echo(f"{label} {lines[0]}")
    continuation = " " * (len(label) + 1)
    for line in lines[1:]:
        typer.echo(f"{continuation}{line}")


def _render_match(match: SearchMatch) -> None:
    candidate = match.candidate
    item = candidate.item
    if isinstance(item, Memory):
        _render_labeled_content(
            f"[memory  {item.uid[:8]}]",
            item.content,
        )
    elif isinstance(item, MemoryRef):
        label = (
            f"[ref     {item.uid[:8]}] "
            f"-> {item.target_context_name}#{item.target_memory_uid[:8]}"
        )
        if item.target is not None:
            _render_labeled_content(label, item.target.content)
        else:
            typer.echo(label)
    elif isinstance(item, QueryContextRef):
        label = f"[query   {item.uid[:8]}]"
        typer.echo(f"{label} {item.name} (query-only)")
        command = shlex.join(
            [
                "mem",
                "query",
                item.name,
                "<question>",
                "--context",
                candidate.context_name,
            ]
        )
        typer.echo(
            f"{' ' * (len(label) + 1)}Ask with: {command}"
        )


def _chat_result(match: SearchMatch, index: int) -> FindChatResult:
    candidate = match.candidate
    item = candidate.item
    if isinstance(item, Memory):
        content = item.content
    elif isinstance(item, MemoryRef):
        content = (
            item.target.content
            if item.target is not None
            else "(dangling reference)"
        )
    elif isinstance(item, QueryContextRef):
        content = f"{item.name} (query-only)"
    else:  # pragma: no cover - SearchMatch validates the result union
        raise FindError("Find returned an unsupported result type.")
    return FindChatResult(
        alias=f"m{index}",
        context_name=candidate.context_name,
        kind={
            "memory": "memory",
            "memory_ref": "ref",
            "query_context": "query",
        }[candidate.kind],
        uid=item.uid,
        content=content,
    )


def _initial_chat_state(
    context_name: str,
    query: str,
    matches: list[SearchMatch],
) -> FindChatState:
    count = len(matches)
    noun = "Memory" if count == 1 else "Memories"
    return FindChatState(
        context_name=context_name,
        current_query=query,
        messages=(
            FindChatMessage(role="USER", text=query),
            FindChatMessage(
                role="MEM",
                text=f"I found {count} matching {noun}.",
            ),
        ),
        results=tuple(
            _chat_result(match, index)
            for index, match in enumerate(matches, start=1)
        ),
        status=(
            "RESULTS READY"
            if matches
            else "NO MATCHING RESULTS"
        ),
    )


def _show_result_proposal(
    state: FindChatState,
    action: FindTurnAction,
    submitted_text: str,
) -> FindShowProposal:
    matches = tuple(
        result
        for result in state.results
        if result.alias == action.selector
    )
    if len(matches) != 1:
        raise FindError(
            "The requested Find result is missing or ambiguous."
        )
    selected = matches[0]
    review = ExactCommandReview(
        argv=(
            "mem",
            "show",
            selected.uid,
            "--context",
            selected.context_name,
        ),
        effects=(
            (
                f"Read-only inspection: SHOW {selected.alias} "
                f"from {selected.context_name}"
            ),
            "Contexts, Memories, checkpoints, and current Context: unchanged",
        ),
    )
    return FindShowProposal(
        action=action,
        result=selected,
        review=review,
        submitted_text=submitted_text,
    )


def _run_read_only_find_command(
    argv: tuple[str, ...],
) -> subprocess.CompletedProcess[str]:
    """Run one allowlisted read-only logical mem argv without a shell."""
    if (
        len(argv) != 5
        or argv[:2] != ("mem", "show")
        or argv[3] != "--context"
        or not argv[2]
        or not argv[4]
    ):
        raise FindError("Find refused a non-show follow-up command.")
    return subprocess.run(
        [sys.executable, "-m", "memcommit.cli", *argv[1:]],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )


def _apply_show_result(
    state: FindChatState,
    proposal: FindShowProposal,
) -> FindChatState:
    try:
        completed = _run_read_only_find_command(proposal.review.argv)
    except subprocess.TimeoutExpired as error:
        raise FindError("The read-only mem show action timed out.") from error
    except OSError as error:
        raise FindError(
            "The read-only mem show action could not be started."
        ) from error
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise FindError(
            "The read-only mem show action failed"
            + (f": {detail}" if detail else ".")
        )
    actual_output = completed.stdout.strip()
    if not actual_output:
        raise FindError(
            "The read-only mem show action returned no output."
        )
    action = proposal.action
    return replace(
        state,
        messages=(
            *state.messages,
            FindChatMessage(
                role="USER",
                text=proposal.submitted_text,
            ),
            FindChatMessage(
                role="MEM",
                text=f"{action.understanding}\n\n{action.question}",
            ),
            FindChatMessage(
                role="STATUS",
                text="\n".join(
                    [
                        "READ-ONLY ACTION · APPLIED",
                        f"  {format_exact_command(proposal.review)}",
                        "",
                        "ACTUAL OUTPUT",
                        actual_output,
                        "",
                        "Find results unchanged.",
                    ]
                ),
            ),
        ),
        status=f"SHOWED {proposal.result.alias} · RESULTS UNCHANGED",
    )


def _handle_find_turn(
    state: FindChatState,
    text: str,
) -> FindChatState:
    turn = interpret_find_turn(
        state,
        text,
        connect_codex_chatgpt_provider,
    )
    if isinstance(turn, FindTurnAsk):
        return replace(
            state,
            messages=(
                *state.messages,
                FindChatMessage(role="USER", text=text),
                FindChatMessage(
                    role="MEM",
                    text=f"{turn.understanding}\n\n{turn.question}",
                ),
            ),
            status="WAITING FOR CLARIFICATION · RESULTS UNCHANGED",
        )
    proposal = _show_result_proposal(state, turn, text)
    # The submitted natural-language turn is the authority for this proven
    # read-only action. Mutating actions will require a separate exact-command
    # approval rather than sharing this immediate execution path.
    return _apply_show_result(state, proposal)


def _run_interactive_find(
    context_name: str,
    query: str,
    matches: list[SearchMatch],
) -> FindChatSessionResult:
    result = run_find_chat_session(
        _initial_chat_state(context_name, query, matches),
        handle_turn=_handle_find_turn,
    )
    typer.echo(
        f"Find dialogue closed with {len(result.state.results)} visible "
        f"result(s) after {len(result.submitted_turns)} follow-up turn(s)."
    )
    return result


def cmd(
    query: Annotated[
        str,
        typer.Argument(help="Natural-language query to find matching items"),
    ],
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Context to search (defaults to current)",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help="Maximum matches to return (1-20)",
        ),
    ] = 5,
    direct: Annotated[
        bool,
        typer.Option(
            "--direct",
            help="Search direct items only; do not descend embedded Contexts",
        ),
    ] = False,
) -> None:
    store = MemoryStore()
    try:
        ctx = (
            store.load_current()
            if context_name is None
            else store.load(context_name)
        )
    except (FileNotFoundError, RuntimeError, ValueError) as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        matches = ops.find(
            ctx,
            query,
            connect_codex_chatgpt_provider,
            recursive=not direct,
            limit=limit,
        )
    except (FindError, QueryProviderError) as e:
        typer.secho(f"Find error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if _interactive_terminal():
        _run_interactive_find(ctx.name, query, matches)
        return

    if not matches:
        typer.secho(ctx.name, bold=True)
        typer.echo("  (no matching items)")
        return

    # Grouping makes the owning Context legible without repeating it on every
    # row. Dict insertion order keeps the model's first Context appearance,
    # while each group's rows retain their relative ranking.
    grouped: dict[tuple[str, str], list[SearchMatch]] = {}
    for match in matches:
        owner = (
            match.candidate.context_uid,
            match.candidate.context_name,
        )
        grouped.setdefault(owner, []).append(match)

    for group_index, ((_, owner_name), owner_matches) in enumerate(
        grouped.items()
    ):
        if group_index:
            typer.echo()
        typer.secho(owner_name, bold=True)
        for match in owner_matches:
            _render_match(match)
