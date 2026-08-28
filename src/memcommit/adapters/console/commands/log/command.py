from collections.abc import Sequence
from dataclasses import replace
from typing import Annotated, Any, Optional

import typer

from memcommit.persistence.command_ledger.attempts import (
    CommandAttempt,
    CommandAttemptError,
    CommandAttemptLedger,
    current_command_attempt_uid,
    annotate_memory_report_attempt,
)
from memcommit.adapters.console.shared.command_progress import CommandProgress
from memcommit.adapters.console.shared.context_operand import ContextOperandSnapshot
from memcommit.adapters.console.shared.history_present import (
    history_result_recovery_label,
)
from memcommit.adapters.console.shared.memory_history import (
    build_memory_history,
    load_retained_history_context,
)
from memcommit.adapters.console.commands.trace.projection import (
    format_compact_trace_report,
)
from memcommit.adapters.console.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.adapters.console.theme import (
    MEMORY_HEX,
    SemanticColorRole,
    semantic_action_role,
    semantic_color_rgb,
)
from memcommit.application.retained_history.display import (
    HistoryDisplayRow,
    HistoryRowSegment,
    history_display_row_segments,
    project_history_display_rows,
)
from memcommit.application.retained_history.reconstruction import HistoryError, build_history
from memcommit.application.operations.log.search import (
    HistorySearchError,
    HistorySearchResult,
    search_history,
)
from memcommit.providers.subscription import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.application.retained_history.memory_history_reconstruction.retained_record_verification import (
    MemoryHistoryReconstructionError,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.config import load_profile_registry
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import MemoryStore
from memcommit.persistence.command_ledger.study_actions import (
    StudyActionError,
    StudyActionEvent,
    StudyActionLedger,
)


def _styled_semantic_label(
    text: str,
    *,
    action: str | None = None,
    role: SemanticColorRole | None = None,
) -> str:
    """Style one trusted label while leaving surrounding report prose neutral."""

    resolved = role if role is not None else semantic_action_role(action or text)
    safe = display_escape_text(text)
    if resolved is None:
        return safe
    return typer.style(safe, fg=semantic_color_rgb(resolved), bold=True)


def _rgb(value: str) -> tuple[int, int, int]:
    return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))


def _styled_history_segment(segment: HistoryRowSegment) -> str:
    if segment.style == "semantic-action":
        return _styled_semantic_label(segment.text, action=segment.action)
    text = display_escape_text(segment.text)
    if segment.style == "memory-object":
        return typer.style(text, fg=_rgb(MEMORY_HEX))
    if segment.style == "history-receipt":
        return typer.style(
            text,
            fg=semantic_color_rgb(SemanticColorRole.HISTORY),
            bold=True,
        )
    if segment.style == "history-source":
        return typer.style(text, bold=True)
    return text


def _history_section(row: HistoryDisplayRow, context_name: str) -> str:
    return (
        f"INHERITED HISTORY · source {row.inherited_from}"
        if row.inherited_from is not None
        else f"DIRECT COMMANDS · {context_name}"
    )


def render_checkpoint_rows(
    entries: Sequence[dict[str, Any]],
    *,
    context_name: str,
    context_uid: str,
    limit: int | None = None,
) -> None:
    """Print retained versions with every visible UID namespace named."""

    selected = entries[:limit] if limit is not None else entries
    rows = project_history_display_rows(
        selected,
        context_name=context_name,
        context_uid=context_uid,
        deduplicate_commands=False,
    )
    last_section: str | None = None
    for row in rows:
        section = _history_section(row, context_name)
        if section != last_section:
            if last_section is not None:
                typer.echo()
            typer.secho(display_escape_text(section), bold=True)
            last_section = section
        # Static Log keeps its established `init` action spelling for scripts
        # while the interactive lifecycle overview uses the clearer `created`
        # label. Both adapters still share the typed UID projection.
        action = "init" if row.is_creation else row.command
        rendered = "".join(
            _styled_history_segment(segment)
            for segment in history_display_row_segments(row, action=action)
        )
        typer.echo(f"  {rendered}")


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
        kind = _styled_semantic_label(
            f"{result.kind:<17}",
            role=SemanticColorRole.HISTORY,
        )
        typer.echo(
            f"  [{kind} {identity[:8]}] "
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
            None
            if attempt.elapsed_seconds is None
            else f"{attempt.elapsed_seconds:.1f}s"
        )
        if attempt.status == "COMPLETED":
            visible_outcome = (
                attempt.outcome.replace("_", " ")
                if attempt.outcome is not None
                else None
            )
        elif attempt.status == "RUNNING":
            # A retained start record proves only that finalization is absent;
            # it cannot safely claim that another process is still alive.
            visible_outcome = "NOT FINALIZED"
        else:
            visible_outcome = attempt.status
        operation = _styled_semantic_label(
            f"{attempt.operation:<16}",
            action=attempt.operation,
        )
        suffix = " · ".join(
            value for value in (visible_outcome, elapsed) if value is not None
        )
        typer.echo(
            f"  [{attempt.uid[:8]}] {display_escape_text(timestamp)}  "
            f"{operation}{suffix}"
        )
        if attempt.command is not None:
            typer.echo(
                "      command=" + display_escape_text(attempt.command)
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
            typer.echo(f"      {kind}{suffix}")


def _missing_study_action_sequences(events: Sequence[StudyActionEvent]) -> int:
    sequences_by_attempt: dict[str, list[int]] = {}
    for event in events:
        sequences_by_attempt.setdefault(event.attempt_uid, []).append(event.sequence)
    return sum(
        max(sequences) - min(sequences) + 1 - len(set(sequences))
        for sequences in sequences_by_attempt.values()
    )


def _render_study_actions(
    events: Sequence[StudyActionEvent],
    *,
    unavailable_sequences: int | None = None,
) -> None:
    typer.secho("Study actions · recent first", bold=True)
    if not events:
        typer.echo("  (no earlier Study actions)")
        return
    missing = (
        _missing_study_action_sequences(events)
        if unavailable_sequences is None
        else unavailable_sequences
    )
    if missing:
        typer.echo(
            f"  WARNING · {missing} earlier event sequence position(s) unavailable."
        )
    for event in events:
        timestamp = event.occurred_at[:19].replace("T", " ")
        elapsed = (
            ""
            if event.elapsed_seconds is None
            else f" +{event.elapsed_seconds:.3f}s"
        )
        action = _styled_semantic_label(event.action, action=event.action)
        typer.echo(
            f"  [{event.attempt_uid[:8]}/{event.sequence}] "
            f"{display_escape_text(timestamp)}{elapsed}  {action}"
        )
        details = " · ".join(
            f"{display_escape_text(key)}={display_escape_text(str(value))}"
            for key, value in sorted(event.data.items())
        )
        if details:
            typer.echo("      " + details)


def cmd(
    query: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Optional natural-language history query; omit to print the "
                "current or explicitly selected Context's checkpoints"
            )
        ),
    ] = None,
    manual: Annotated[bool, typer.Option("--manual", "-m", help="Show only manually-created checkpoints")] = False,
    plain: Annotated[
        bool,
        typer.Option(
            "--plain",
            help="Compatibility option; Log always prints stable rows",
        ),
    ] = False,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help="Maximum semantic matches or Memory-lineage operations (1-20)",
        ),
    ] = 20,
    operations: Annotated[
        bool,
        typer.Option(
            "--operations",
            help=(
                "Show Profile-scoped mem command attempts, including entered "
                "commands, instead of Context checkpoints"
            ),
        ),
    ] = False,
    actions: Annotated[
        bool,
        typer.Option(
            "--actions",
            help=(
                "Show detailed actions for the active init-study Profile; "
                "Participant command and Help lookup text are retained"
            ),
        ),
    ] = False,
    memory: Annotated[
        Optional[str],
        typer.Option(
            "--memory",
            help=(
                "Inspect one current or historical Memory lineage; "
                "mem trace provides interactive inspection of the same lineage"
            ),
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Context whose retained history to inspect (defaults to current)",
        ),
    ] = None,
) -> None:
    # Log is deliberately terminal-independent. Keep --plain accepted for
    # existing scripts, but never let terminal capability change this report.
    del plain
    if operations and actions:
        typer.secho(
            "--operations and --actions are separate log views.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if actions:
        if query is not None or manual or memory is not None or context_name is not None:
            typer.secho(
                "--actions cannot be combined with a history query, "
                "--manual, --memory, or --context.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if not 1 <= limit <= 1000:
            typer.secho(
                "--limit must be between 1 and 1000 for Study actions.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        store = MemoryStore(create=False)
        try:
            current_uid = current_command_attempt_uid()
            profile = load_profile_registry().active
            all_events = tuple(
                event
                for event in StudyActionLedger(
                    profile,
                    store_dir=store.store_dir,
                ).list()
                if event.attempt_uid != current_uid
            )
        except (OSError, ProfileConfigError, StudyActionError) as error:
            typer.secho(
                f"Study action log error: {display_escape_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        _render_study_actions(
            all_events[:limit],
            unavailable_sequences=_missing_study_action_sequences(all_events),
        )
        return

    if operations:
        if query is not None or manual or memory is not None or context_name is not None:
            typer.secho(
                "--operations cannot be combined with a history query, "
                "--manual, --memory, or --context.",
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
    try:
        context_snapshot = ContextOperandSnapshot.capture(store)
        name = context_snapshot.resolve_or_current(context_name)
    except ValueError as error:
        typer.secho(
            f"History Context error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if memory is not None:
        if query is not None or manual:
            typer.secho(
                "--memory cannot be combined with a history query or --manual.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if not 1 <= limit <= 20:
            typer.secho(
                "--limit must be between 1 and 20 for Memory lineage output.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if not name:
            typer.secho(
                "No current context. Pass --context or run 'mem init <name>' first.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        try:
            history_context = load_retained_history_context(
                store,
                context_locator=name if context_name is not None else None,
                current_name=context_snapshot.current_name,
            )
            report = build_memory_history(store, history_context, memory)
            annotate_memory_report_attempt(
                operation="trace",
                context_name=history_context.display_name,
                memory_uid=report.selected_uid,
            )
        except (
            FileNotFoundError,
            OSError,
            RuntimeError,
            ValueError,
            MemoryHistoryReconstructionError,
            ProfileConfigError,
            ProfileError,
            PermissionError,
        ) as error:
            typer.secho(
                f"Log Memory error: {display_escape_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        typer.echo(format_compact_trace_report(report, limit=limit))
        return

    if not name:
        typer.secho("No current context. Run 'mem init <name>' first.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    context = store.load_direct(name)
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
            with CommandProgress(
                "LOG",
                "connecting provider",
                total=2,
            ) as progress:
                provider = connect_codex_chatgpt_provider()
                progress.update("searching history", step=2)
                results = search_history(
                    timeline,
                    query,
                    provider,
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
        _render_history_results(name, results)
        return

    if not entries:
        msg = "No manual checkpoints" if manual else "No checkpoints"
        typer.echo(f"{msg} for '{name}' yet.")
        return

    typer.secho(f"Log for '{name}':", bold=True)
    typer.echo()
    render_checkpoint_rows(
        entries,
        context_name=name,
        context_uid=context.uid,
    )
