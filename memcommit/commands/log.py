from collections.abc import Sequence
from dataclasses import replace
import sys
from typing import Annotated, Any, Optional

import typer

from memcommit.command_attempts import (
    CommandAttempt,
    CommandAttemptError,
    CommandAttemptLedger,
    current_command_attempt_uid,
)
from memcommit.commands.history_picker import choose_history
from memcommit.commands.history_present import (
    checkpoint_picker_entries,
    history_result_recovery_label,
    history_result_picker_entries,
)
from memcommit.commands.tui_primitives import display_escape_text, safe_terminal_text
from memcommit.history import HistoryError, build_history
from memcommit.history_search import (
    HistorySearchError,
    HistorySearchResult,
    search_history,
)
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.store import MemoryStore


def render_checkpoint_rows(entries: Sequence[dict[str, Any]], limit: int | None = None) -> None:
    rows = entries[:limit] if limit is not None else entries
    for cp in rows:
        ts = cp["timestamp"][:16].replace("T", " ")
        uid_short = cp["uid"][:8]
        is_auto = cp.get("auto", False)
        command = cp.get("command") or "checkpoint"
        label = " ".join((cp.get("description") or cp.get("message") or "(no message)").split())

        if is_auto:
            typer.secho(f"  {uid_short}  {ts}  {command:<12}  {label}")
        else:
            msg = cp.get("message") or "(no message)"
            typer.secho(f"  {uid_short}  {ts}  {'checkpoint':<12}  {msg}", fg=typer.colors.CYAN, bold=True)


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _render_history_results(
    context_name: str,
    results: Sequence[HistorySearchResult],
) -> None:
    typer.secho(f"History matches for '{context_name}':", bold=True)
    if not results:
        typer.echo("  (no matching historical items)")
        return
    for result in results:
        timestamp = (
            result.timestamp[:16].replace("T", " ")
            if result.timestamp
            else "current"
        )
        identity = result.checkpoint_uid or result.candidate_id
        typer.echo(
            f"  [{result.kind:<17} {identity[:8]}] "
            f"{display_escape_text(timestamp)}  "
            f"{display_escape_text(result.description)}  "
            f"({display_escape_text(history_result_recovery_label(result))})"
        )


def _render_operation_attempts(attempts: Sequence[CommandAttempt]) -> None:
    typer.secho("Operation attempts · recent first", bold=True)
    if not attempts:
        typer.echo("  (no earlier command attempts)")
        return
    for attempt in attempts:
        timestamp = attempt.started_at[:16].replace("T", " ")
        elapsed = (
            "running"
            if attempt.elapsed_seconds is None
            else f"{attempt.elapsed_seconds:.1f}s"
        )
        typer.echo(
            f"  [{attempt.uid[:8]}] {display_escape_text(timestamp)}  "
            f"{attempt.status:<11} {attempt.operation:<16} {elapsed}"
        )
        sever = attempt.details.get("sever")
        if isinstance(sever, dict):
            source = sever.get("source_name")
            criteria = sever.get("criteria_name")
            source_count = sever.get("source_memory_count")
            criteria_count = sever.get("criteria_memory_count")
            output = sever.get("output_name")
            if all(
                value is not None
                for value in (source, criteria, source_count, criteria_count, output)
            ):
                typer.echo(
                    "      SEVER · "
                    f"{safe_terminal_text(str(source))} ({source_count}) × "
                    f"{safe_terminal_text(str(criteria))} ({criteria_count}) → "
                    f"{safe_terminal_text(str(output))}"
                )
            provider = sever.get("provider")
            timeout = sever.get("provider_timeout_seconds")
            failure_kind = sever.get("failure_kind")
            if provider is not None or timeout is not None or failure_kind is not None:
                detail = []
                if provider is not None:
                    detail.append(f"provider {safe_terminal_text(str(provider))}")
                if timeout is not None:
                    detail.append(f"timeout {timeout:g}s")
                if failure_kind is not None:
                    detail.append(f"failure {safe_terminal_text(str(failure_kind))}")
                typer.echo("      " + " · ".join(detail))
        if attempt.failure is not None:
            kind = safe_terminal_text(str(attempt.failure["kind"]))
            exit_code = attempt.failure.get("exit_code")
            suffix = f" · exit {exit_code}" if exit_code is not None else ""
            typer.echo(f"      COMMAND · {kind}{suffix}")


def cmd(
    query: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Optional natural-language history query; omit to show all "
                "checkpoints"
            )
        ),
    ] = None,
    manual: Annotated[bool, typer.Option("--manual", "-m", help="Show only manually-created checkpoints")] = False,
    plain: Annotated[
        bool,
        typer.Option(
            "--plain",
            help="Print rows instead of opening the terminal history picker",
        ),
    ] = False,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help="Maximum semantic history matches to return (1-20)",
        ),
    ] = 20,
    operations: Annotated[
        bool,
        typer.Option(
            "--operations",
            help="Show Profile-scoped mem command attempts instead of Context checkpoints",
        ),
    ] = False,
) -> None:
    if operations:
        if query is not None or manual:
            typer.secho(
                "--operations cannot be combined with a history query or --manual.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if not 1 <= limit <= 200:
            typer.secho(
                "--limit must be between 1 and 200 for operation attempts.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        store = MemoryStore(create=False)
        try:
            current_uid = current_command_attempt_uid()
            attempts = tuple(
                attempt
                for attempt in CommandAttemptLedger(store.store_dir).list()
                if attempt.uid != current_uid
            )[:limit]
        except CommandAttemptError as error:
            typer.secho(
                f"Operation log error: {display_escape_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        _render_operation_attempts(attempts)
        return

    store = MemoryStore()
    name = store.current_context_name()
    if not name:
        typer.secho("No current context. Run 'mem init <name>' first.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    all_entries = store.list_checkpoints(name)
    entries = all_entries
    if manual:
        entries = [e for e in entries if not e.get("auto", False)]

    if query is not None:
        try:
            timeline = build_history(store, name)
            if manual:
                # Restrict result candidates before semantic reduction. If
                # filtering happened afterward, an automatic head selected
                # by LATEST could hide the actual latest manual checkpoint.
                timeline = replace(
                    timeline,
                    checkpoints=tuple(
                        checkpoint
                        for checkpoint in timeline.checkpoints
                        if checkpoint.selectable and not checkpoint.auto
                    ),
                )
            results = search_history(
                timeline,
                query,
                connect_codex_chatgpt_provider(),
                result_kinds=("checkpoint",),
                limit=limit,
            )
        except (HistoryError, HistorySearchError, QueryProviderError) as error:
            typer.secho(
                f"History search error: {error}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if not results:
            _render_history_results(name, ())
            return
        if _interactive_terminal() and not plain:
            try:
                choose_history(
                    history_result_picker_entries(results),
                    context_name=name,
                    mode="log",
                )
            except ValueError as error:
                typer.secho(
                    f"History picker error: {error}",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(1)
            return
        _render_history_results(name, results)
        return

    if not entries:
        msg = "No manual checkpoints" if manual else "No checkpoints"
        typer.echo(f"{msg} for '{name}' yet.")
        return

    if _interactive_terminal() and not plain:
        try:
            projected = {
                entry.uid: entry
                for entry in checkpoint_picker_entries(all_entries)
            }
            choose_history(
                [
                    projected[entry["uid"]]
                    for entry in entries
                ],
                context_name=name,
                mode="log",
            )
        except ValueError as error:
            typer.secho(
                f"History picker error: {error}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        return

    typer.secho(f"Log for '{name}':", bold=True)
    typer.echo()
    render_checkpoint_rows(entries)
