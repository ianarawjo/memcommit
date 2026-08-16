"""Plan and exactly apply confirmed duplicate components."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.clipboard import write_system_clipboard
from memcommit.dedup_application import (
    DedupConflictError,
    DedupError,
    DedupRequest,
    DedupSelection,
    apply_dedup,
    prepare_dedup,
)
from memcommit.dedup_runtime import MemoryStoreDedupPort
from memcommit.interfaces.cli.dedup import (
    render_dedup_plan_plain,
    render_dedup_receipt,
)
from memcommit.interfaces.console import (
    ConsoleMode,
    ConsoleModeError,
    SystemTerminalCapabilities,
    resolve_console_mode,
)
from memcommit.interfaces.console.text import display_escape_text
from memcommit.interfaces.tui.operations.dedup import run_dedup_tui
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.quality_finding_handoff import (
    QualityFindingHandoffError,
    quality_finding_handoff_from_json,
)
from memcommit.store import ConcurrentContextUpdateError, MemoryStore


def _selection(value: str) -> DedupSelection:
    if value.count("=") != 1:
        raise DedupError("Dedup --survivor must be COMPONENT=MEMORY.")
    component_uid, survivor_uid = value.split("=", 1)
    return DedupSelection(component_uid, survivor_uid)


def cmd(
    finding_handoffs: Annotated[
        Optional[list[str]],
        typer.Option(
            "--finding-handoff",
            help="Canonical duplicate handoff JSON; repeat for every confirmed link",
        ),
    ] = None,
    survivors: Annotated[
        Optional[list[str]],
        typer.Option(
            "--survivor",
            help="Exact COMPONENT=MEMORY survivor decision; repeat per component",
        ),
    ] = None,
    expected_revision: Annotated[
        Optional[str],
        typer.Option(
            "--expected-revision",
            help="Exact frozen revision printed by the reviewed Dedup plan",
        ),
    ] = None,
    apply_now: Annotated[
        bool,
        typer.Option("--apply", help="Apply the exact complete survivor set"),
    ] = False,
    plain: Annotated[
        bool,
        typer.Option("--plain", help="Print the plan or receipt instead of the TUI"),
    ] = False,
    tui: Annotated[
        bool,
        typer.Option("--tui", help="Require the interactive Dedup review flow"),
    ] = False,
) -> None:
    """Keep one existing Memory per confirmed duplicate component."""

    try:
        mode = resolve_console_mode(plain=plain, tui=tui)
        if not finding_handoffs:
            raise DedupError(
                "Dedup requires at least one --finding-handoff from find-duplicates."
            )
        if apply_now:
            if not survivors or expected_revision is None:
                raise DedupError(
                    "Dedup --apply requires --survivor and --expected-revision."
                )
            if mode is ConsoleMode.TUI:
                raise DedupError(
                    "Dedup --apply is already exact; do not combine it with --tui."
                )
        elif survivors or expected_revision is not None:
            raise DedupError(
                "Dedup --survivor and --expected-revision require --apply."
            )
        request = DedupRequest(
            tuple(quality_finding_handoff_from_json(item) for item in finding_handoffs)
        )
        store = MemoryStore(create=False)
        try:
            current_name = store.current_context_name()
        except FileNotFoundError:
            current_name = None
        port = MemoryStoreDedupPort(store, current_name=current_name)
        plan = prepare_dedup(request, port=port)
        if expected_revision is not None and plan.revision != expected_revision:
            raise DedupConflictError(
                "The reviewed Dedup revision was not regenerated; nothing was written."
            )
        if apply_now:
            receipt = apply_dedup(
                plan,
                tuple(_selection(value) for value in survivors or ()),
                port=port,
            )
            render_dedup_receipt(receipt)
            return
        interactive = SystemTerminalCapabilities().is_interactive()
        selected_mode = (
            ConsoleMode.TUI
            if mode is ConsoleMode.AUTO and interactive
            else ConsoleMode.PLAIN
            if mode is ConsoleMode.AUTO
            else mode
        )
        if selected_mode is ConsoleMode.TUI:
            run_dedup_tui(
                plan,
                apply_selections=lambda values: apply_dedup(
                    plan,
                    values,
                    port=port,
                ),
                clipboard_writer=write_system_clipboard,
            )
        else:
            render_dedup_plan_plain(plan)
    except (
        ConcurrentContextUpdateError,
        ConsoleModeError,
        DedupError,
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QualityFindingHandoffError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        typer.secho(
            "Dedup error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)


__all__ = ["cmd"]
