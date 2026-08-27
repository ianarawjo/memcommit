"""Compatibility adapter for the exact semantic-Dedun review replay."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.infrastructure.clipboard import write_system_clipboard
from memcommit.application.operations.dedup.application import (
    DedupConflictError,
    DedupError,
    DedupRequest,
    DedupSelection,
    apply_dedup,
    prepare_dedup,
)
from memcommit.application.operations.dedup.runtime import MemoryStoreDedupPort
from memcommit.adapters.interfaces.cli.dedup import (
    render_dedup_plan_plain,
    render_dedup_receipt,
)
from memcommit.adapters.interfaces.console import (
    ConsoleMode,
    ConsoleModeError,
    SystemTerminalCapabilities,
    resolve_console_mode,
)
from memcommit.adapters.interfaces.console.text import display_escape_text
from memcommit.adapters.interfaces.tui.operations.dedup import run_dedup_tui
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.application.reviewing.quality.handoff import (
    QualityFindingHandoffError,
)
from memcommit.semantic.redundancy_evidence import (
    redundancy_evidence_from_json,
)
from memcommit.persistence.store import ConcurrentContextUpdateError, MemoryStore


def _selection(value: str) -> DedupSelection:
    if value.count("=") != 1:
        raise DedupError("Dedun --survivor must be COMPONENT=MEMORY.")
    component_uid, survivor_uid = value.split("=", 1)
    return DedupSelection(component_uid, survivor_uid)


def cmd(
    evidence: Annotated[
        Optional[list[str]],
        typer.Option(
            "--evidence",
            help=(
                "Canonical confirmed redundancy evidence JSON; repeat for "
                "every link"
            ),
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
            help="Reviewed Context revision required to apply",
        ),
    ] = None,
    apply_now: Annotated[
        bool,
        typer.Option("--apply", help="Apply the reviewed survivor decisions"),
    ] = False,
    plain: Annotated[
        bool,
        typer.Option("--plain", help="Print the plan or receipt instead of the TUI"),
    ] = False,
    tui: Annotated[
        bool,
        typer.Option("--tui", help="Require the semantic redundancy review flow"),
    ] = False,
) -> None:
    """Apply confirmed semantic redundancies, retaining existing wording."""

    try:
        mode = resolve_console_mode(plain=plain, tui=tui)
        if not evidence:
            raise DedupError(
                "Dedun requires exact or semantic redundancy evidence from its review."
            )
        if apply_now:
            if not survivors or expected_revision is None:
                raise DedupError(
                    "Dedun --apply requires --survivor and "
                    "--expected-revision."
                )
            if mode is ConsoleMode.TUI:
                raise DedupError(
                    "Dedun --apply is already exact; do not combine it "
                    "with --tui."
                )
        elif survivors or expected_revision is not None:
            raise DedupError(
                "Dedun --survivor and --expected-revision require --apply."
            )
        handoffs = tuple(
            redundancy_evidence_from_json(item) for item in evidence
        )
        request = DedupRequest(
            handoffs,
            exact_source=handoffs[0].sources[0],
            exact_source_frame_digest=handoffs[0].source_frame_digest,
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
                "The reviewed consolidation revision was not regenerated; "
                "nothing was written."
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
            "Dedun error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)


__all__ = ["cmd"]
