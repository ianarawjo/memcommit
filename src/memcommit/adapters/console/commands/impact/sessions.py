"""Impact projections for already-saved operation sessions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import sys

import typer

from memcommit.adapters.console.terminal.components.resolution.session_shell import (
    SessionTodoView,
    resolution_report_fragments,
    resolution_seeded_report_fragments,
    run_resolution_workbench_shell,
)
from memcommit.adapters.console.commands.impact.projection import ImpactController
from memcommit.adapters.console.terminal.components.resolution.effect_preview import (
    EffectReportPresentation,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.presentation.effect_report import (
    effect_report_fragments,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.presentation.reporting import (
    _current_impact,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.capabilities.reviewing.memory_diff import (
    update_operation_change,
)
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionWorkbenchView,
)
from memcommit.application.operations.sever.model import SeverSession
from memcommit.application.operations.sever.resolution_adapter import (
    SeverResolutionWorkbenchAdapter,
    sever_memory_changes,
)
from memcommit.application.operations.update.model import (
    UpdateContextInputs,
    UpdatePlan,
)
from memcommit.adapters.console.commands.update.effects import (
    update_effect_view,
    update_effect_report,
)


@dataclass(frozen=True)
class ImpactSessionPresentation:
    """One revision-bound effect surface with an optional Apply handoff."""

    view: ResolutionWorkbenchView
    controller: ImpactController
    report_text: str = ""
    handoff_available: bool = True
    show_impact_ledger: bool = True
    effect_report: EffectReportPresentation | None = None

    @property
    def visible_impact_controller(self) -> ImpactController | None:
        """Return the effect ledger only when it adds a distinct reading."""

        return self.controller if self.show_impact_ledger else None


def update_impact_presentation(
    inputs: UpdateContextInputs,
    plan: UpdatePlan,
    *,
    completed=False,
) -> ImpactSessionPresentation:
    """Project one saved Update receipt as exact located Memory changes."""

    view = update_effect_view(inputs, plan, completed=completed)
    return ImpactSessionPresentation(
        view=view,
        controller=ImpactController.from_memory_changes(
            operation=view.operation,
            artifact_uid=view.artifact_uid,
            revision=view.revision,
            title="IMPACT · UPDATE",
            summary="Recorded Update changes."
            if completed
            else "Proposed Update changes; nothing applied.",
            changes=tuple(
                update_operation_change(operation) for operation in plan.operations
            ),
        ),
        handoff_available=False,
        effect_report=update_effect_report(plan),
    )


def sever_impact_presentation(session: SeverSession) -> ImpactSessionPresentation:
    """Project one saved Sever result with its exact save mode."""

    view = SeverResolutionWorkbenchAdapter(session).view()
    self_save = session.save_mode == "SELF_SAVE"
    summary = (
        "This is the exact local result "
        + (
            "recorded as saved. "
            if session.state == "APPLIED"
            else "that Apply would save. "
        )
        + (
            "It replaces the Source Context."
            if self_save
            else "The Source Context remains unchanged."
        )
    )
    return ImpactSessionPresentation(
        view=view,
        controller=ImpactController.from_memory_changes(
            operation=view.operation,
            artifact_uid=view.artifact_uid,
            revision=view.revision,
            title=(
                "IMPACT · SEVER SELF-SAVE · SOURCE WILL BE REPLACED"
                if self_save
                else "IMPACT · SEVER OTHER-SAVE"
            ),
            summary=summary,
            changes=sever_memory_changes(session),
        ),
        handoff_available=session.state == "REVIEWING",
    )


def _apply_handoff(presentation: ImpactSessionPresentation) -> SessionTodoView:
    operation = presentation.view.operation.title()
    return SessionTodoView(
        "APPLY?",
        f"Continue to {operation} Apply",
        (
            ""
            if presentation.effect_report is not None
            else f"Enter to open the owning {operation} workflow; this choice does "
            "not apply anything yet."
        ),
    )


def render_impact_session_snapshot(
    presentation: ImpactSessionPresentation,
) -> str:
    """Render the Impact ledger and its available owning-operation route."""

    if presentation.effect_report is not None:
        impact = _current_impact(presentation.controller, presentation.view)
        assert impact is not None
        fragments = effect_report_fragments(
            presentation.view,
            impact,
            presentation.effect_report,
            focused_section=-1,
            expanded_uid=None,
            content_width=176,
        )
    elif presentation.report_text:
        fragments = resolution_seeded_report_fragments(
            presentation.view,
            presentation.report_text,
            read_only=True,
            impact_controller=presentation.visible_impact_controller,
        )
    else:
        fragments = resolution_report_fragments(
            presentation.view,
            read_only=True,
            impact_controller=presentation.visible_impact_controller,
        )
    rendered = "".join(
        text for style, text in fragments if style != "[SetCursorPosition]"
    ).rstrip()
    if not presentation.handoff_available:
        return rendered
    handoff = _apply_handoff(presentation)
    return f"{rendered}\n\nTO DO\n[ {handoff.kind} ]  {handoff.label}" + (
        f" · {handoff.detail}" if handoff.detail else ""
    )


def run_impact_session_workbench(
    presentation: ImpactSessionPresentation,
    *,
    terminal_label: str,
) -> bool:
    """Browse one saved Impact and optionally request an owning-flow handoff."""

    action = run_resolution_workbench_shell(
        presentation.view,
        terminal_label=terminal_label,
        snapshot_hint=(
            "Run the same 'mem impact OPERATION' command outside a TTY for a snapshot."
        ),
        split_viewer_items=True,
        split_report_text=presentation.report_text or None,
        read_only=True,
        read_only_handoff=(
            _apply_handoff(presentation) if presentation.handoff_available else None
        ),
        impact_controller=presentation.visible_impact_controller,
        effect_report=presentation.effect_report,
    )
    if action.kind == "HANDOFF" and presentation.handoff_available:
        return True
    if action.kind == "CLOSE":
        return False
    # Impact itself has no mutation action. Only the explicit handoff above
    # may leave this surface, and the owning workflow must revalidate again.
    raise ValueError("A standalone Impact view returned an invalid action.")


def show_saved_impact(
    presentation: ImpactSessionPresentation,
    *,
    kind: str,
) -> bool:
    """Present one saved artifact and report an explicit Apply handoff."""

    if sys.stdin.isatty() and sys.stdout.isatty():
        handoff = run_impact_session_workbench(
            presentation,
            terminal_label=f"Interactive saved {kind.title()} Impact",
        )
        if not handoff:
            typer.echo(f"{kind.title()} Impact closed.")
        return handoff
    typer.echo(render_impact_session_snapshot(presentation))
    return False


def run_saved_impact_handoff_loop(
    *,
    load_presentation: Callable[[], ImpactSessionPresentation],
    open_owning_workflow: Callable[[], None],
    kind: str,
) -> None:
    """Return a cancelled final Apply to its exact saved Impact surface."""

    while True:
        presentation = load_presentation()
        if not show_saved_impact(presentation, kind=kind):
            return
        open_owning_workflow()
        refreshed = load_presentation()
        if not refreshed.handoff_available:
            return


def show_process_local_impact(
    presentation: ImpactSessionPresentation,
    *,
    operation: str,
) -> None:
    """Render a prepared artifact without manufacturing an Apply handoff."""

    if sys.stdin.isatty() and sys.stdout.isatty():
        run_impact_session_workbench(
            presentation,
            terminal_label=f"Interactive {operation.title()} Impact",
        )
        typer.echo(f"{operation.title()} Impact closed.")
        return
    typer.echo(render_impact_session_snapshot(presentation))


def process_local_impact_error(operation: str, error: BaseException) -> None:
    """Translate one operation-owned process-local failure to the CLI contract."""

    typer.secho(
        f"Impact {operation} error: {display_escape_text(str(error))}",
        fg=typer.colors.RED,
        err=True,
    )
    raise typer.Exit(1)
