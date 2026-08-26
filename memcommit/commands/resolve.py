"""Generate and explicitly apply grounded Fit-repair candidates."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.clipboard import write_system_clipboard
from memcommit.commands.command_progress import CommandProgress
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.operations.fit.judgment import FitJudgmentError
from memcommit.interfaces.cli.resolve import (
    render_resolve_plain,
    render_resolve_receipt,
)
from memcommit.interfaces.console import (
    ConsoleMode,
    ConsoleModeError,
    SystemTerminalCapabilities,
    resolve_console_mode,
)
from memcommit.interfaces.console.text import display_escape_text
from memcommit.interfaces.tui.operations.resolve import run_resolve_tui
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.query_provider import QueryProviderError, connect_semantic_provider
from memcommit.operations.resolve.application import (
    ResolveError,
    ResolveRequest,
    apply_resolve,
    run_resolve,
)
from memcommit.operations.resolve.runtime import MemoryStoreResolvePort
from memcommit.operations.resolve.semantic import ProviderResolveSemanticPort
from memcommit.operations.resolve.targeting import normalize_resolve_cli_targets
from memcommit.quality_finding_handoff import (
    QualityFindingHandoffError,
    conflict_handoff_to_resolve_request,
    quality_finding_handoff_from_json,
)
from memcommit.store import MemoryStore


def cmd(
    auto_operands: Annotated[
        Optional[list[str]],
        typer.Argument(
            help=(
                "Auto operand: existing Context locator, Memory UID prefix, "
                "or CONTEXT:UID; omit to use the current Context"
            )
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Exact local Context or readable granted Context to repair",
        ),
    ] = None,
    memory_operands: Annotated[
        Optional[list[str]],
        typer.Option(
            "--memory",
            metavar="[CONTEXT:]UID_OR_PREFIX",
            help=(
                "Repeatable direct Memory restriction; short prefixes are "
                "accepted because --memory makes their role explicit"
            ),
        ),
    ] = None,
    allow_create: Annotated[
        bool,
        typer.Option(
            "--allow-create/--no-create",
            help=(
                "Allow the automatic interpretation plan to add grounded direct "
                "Memories; enabled by default"
            ),
        ),
    ] = True,
    allow_delete: Annotated[
        bool,
        typer.Option(
            "--allow-delete",
            help="Permit guidance-grounded deletion candidates",
        ),
    ] = False,
    guidance: Annotated[
        Optional[str],
        typer.Option(
            "--guidance",
            help="Grounding instruction or fact available to candidate generation",
        ),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            help="Require an exact YES resolution whose post-image also Fits as YES",
        ),
    ] = False,
    finding_handoff: Annotated[
        Optional[str],
        typer.Option(
            "--finding-handoff",
            help="Canonical conflict handoff JSON emitted by find-conflicts",
        ),
    ] = None,
    candidate_uid: Annotated[
        Optional[str],
        typer.Option(
            "--candidate",
            help="Exact full candidate id from a reviewed Resolve analysis",
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
        typer.Option(
            "--apply",
            help="Apply the exact regenerated candidate after Fit verification",
        ),
    ] = False,
    plain: Annotated[
        bool,
        typer.Option(
            "--plain",
            help="Print non-applicable outcomes instead of opening the TUI",
        ),
    ] = False,
    tui: Annotated[
        bool,
        typer.Option(
            "--tui",
            help="Require an interactive view for non-applicable outcomes",
        ),
    ] = False,
) -> None:
    """Make one complete Memory frame Fit through grounded minimum changes."""

    try:
        mode = resolve_console_mode(plain=plain, tui=tui)
        # A terminal outcome is still a result, not an invitation to inspect a
        # report. Keep the Viewer behind the explicit --tui route.
        if mode is ConsoleMode.AUTO:
            mode = ConsoleMode.PLAIN
        if apply_now:
            if candidate_uid is None or expected_revision is None:
                raise ResolveError(
                    "Resolve --apply requires --candidate and --expected-revision."
                )
            if mode is ConsoleMode.TUI:
                raise ResolveError(
                    "Resolve --apply is already exact; do not combine it with --tui."
                )
        elif candidate_uid is not None or expected_revision is not None:
            raise ResolveError(
                "Resolve --candidate and --expected-revision require --apply."
            )

        store = MemoryStore(create=False)
        snapshot = ContextOperandSnapshot.capture(store)
        if finding_handoff is not None:
            if context_name is not None or auto_operands or memory_operands:
                raise ResolveError(
                    "Resolve --finding-handoff cannot be combined with a Context "
                    "or Memory selector."
                )
            request = conflict_handoff_to_resolve_request(
                quality_finding_handoff_from_json(finding_handoff),
                allow_create=allow_create,
                allow_delete=allow_delete,
                guidance=guidance or "",
                target_fit="YES" if yes else "MAY",
            )
        else:
            targets = normalize_resolve_cli_targets(
                store,
                tuple(auto_operands or ()),
                context_locator=context_name,
                memory_operands=tuple(memory_operands or ()),
                current_context_name=snapshot.current_name,
            )
            request = ResolveRequest(
                context_name=targets.context_name,
                memory_selectors=targets.memory_selectors,
                allow_create=allow_create,
                allow_delete=allow_delete,
                guidance=guidance or "",
                target_fit="YES" if yes else "MAY",
            )
        port = MemoryStoreResolvePort(
            store,
            current_name=snapshot.current_name,
        )
        with CommandProgress(
            "RESOLVE",
            "building and checking repair",
            total=1,
        ) as progress:
            analysis = run_resolve(
                request,
                frame_port=port,
                semantic_port=ProviderResolveSemanticPort(),
                provider_factory=connect_semantic_provider,
                expected_revision=expected_revision,
            )
            progress.update("repair ready", step=1)

        if apply_now:
            assert candidate_uid is not None
            receipt = apply_resolve(
                analysis,
                candidate_uid,
                frame_port=port,
            )
            candidate = next(
                candidate
                for candidate in analysis.candidates
                if candidate.uid == receipt.candidate_uid
            )
            render_resolve_receipt(
                receipt,
                fit_verdict=candidate.fit.verdict,
            )
            return

        # A PROPOSAL is already the operation-owned, independently Fit-verified
        # unique judgment. Resolve is an execution command, so that judgment is
        # applied atomically here; the full reasoning remains available later
        # through the immutable checkpoint Review.
        if analysis.status == "PROPOSAL":
            candidate = analysis.candidates[0]
            receipt = apply_resolve(
                analysis,
                candidate.uid,
                frame_port=port,
            )
            render_resolve_receipt(
                receipt,
                fit_verdict=candidate.fit.verdict,
            )
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
            run_resolve_tui(
                analysis,
                apply_candidate=lambda selected: apply_resolve(
                    analysis,
                    selected,
                    frame_port=port,
                ),
                clipboard_writer=write_system_clipboard,
            )
        else:
            render_resolve_plain(analysis)
    except (
        ConsoleModeError,
        FileNotFoundError,
        FitJudgmentError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        QualityFindingHandoffError,
        ResolveError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        typer.secho(
            "Resolve error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)


__all__ = ["cmd"]
