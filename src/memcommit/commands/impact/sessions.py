"""Impact projections for already-saved operation sessions."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.commands.shared.resolution_workbench_shell import (
    SessionTodoView,
    resolution_report_fragments,
    resolution_seeded_report_fragments,
    run_resolution_workbench_shell,
)
from memcommit.interfaces.tui.workbenches.impact import ImpactController
from memcommit.application.reviewing.memory_diff import update_operation_change
from memcommit.operations.meld.model import MeldSession
from memcommit.operations.meld.resolution_adapter import MeldResolutionWorkbenchAdapter
from memcommit.resolution.workbench import ResolutionWorkbenchView
from memcommit.operations.sever.model import SeverSession
from memcommit.operations.sever.resolution_adapter import (
    SeverResolutionWorkbenchAdapter,
    sever_memory_changes,
)
from memcommit.operations.update.model import UpdateSession
from memcommit.operations.update.resolution_adapter import UpdateResolutionWorkbenchAdapter


@dataclass(frozen=True)
class ImpactSessionPresentation:
    """One revision-bound effect surface with an optional Apply handoff."""

    view: ResolutionWorkbenchView
    controller: ImpactController
    report_text: str = ""
    handoff_available: bool = True
    show_impact_ledger: bool = True

    @property
    def visible_impact_controller(self) -> ImpactController | None:
        """Return the effect ledger only when it adds a distinct reading."""

        return self.controller if self.show_impact_ledger else None


def update_impact_presentation(
    session: UpdateSession,
) -> ImpactSessionPresentation:
    """Project one saved Update receipt as exact located Memory changes."""

    view = UpdateResolutionWorkbenchAdapter(session).view()
    state_summary = {
        "impact": "These exact target changes are planned. Nothing is applied.",
        "staged": (
            "These exact target changes are staged. Apply remains a separate "
            "operation."
        ),
        "applied": "These are the exact target changes recorded as applied.",
        "undone": "These are the exact target changes recorded as undone.",
    }.get(session.status, "These are the exact changes in the saved Update receipt.")
    return ImpactSessionPresentation(
        view=view,
        controller=ImpactController.from_memory_changes(
            operation=view.operation,
            artifact_uid=view.artifact_uid,
            revision=view.revision,
            title="IMPACT · UPDATE",
            summary=state_summary,
            changes=tuple(
                update_operation_change(operation)
                for operation in session.operations
            ),
        ),
        handoff_available=session.status in {"impact", "staged"},
    )


def _saved_compare_report(session: MeldSession) -> str:
    if session.mode != "SYMMETRIC" or session.comparison_seed is None:
        return ""
    from memcommit.interfaces.presentation.comparison import render_comparison

    return (
        render_comparison(
            session.comparison_seed.analysis,
            reused=True,
            durable=True,
        )
        .partition("\nThe complete source-linked relation ledger")[0]
        .rstrip()
    )


def meld_impact_presentation(session: MeldSession) -> ImpactSessionPresentation:
    """Project one saved Meld assessment without mutating it."""

    if session.current_assessment is None:
        raise ValueError(
            "The saved Meld has no assessed proposal to show as Impact."
        )
    view = MeldResolutionWorkbenchAdapter(session).view()
    compare_report = _saved_compare_report(session)
    controller = (
        ImpactController.from_text(
            operation=view.operation,
            artifact_uid=view.artifact_uid,
            revision=view.revision,
            title="IMPACT · COMPARE",
            summary=(
                "This saved equal-authority Compare analysis is the symmetric "
                "Meld impact."
            ),
            detail=compare_report,
        )
        if compare_report
        else ImpactController.from_resolution(
            view,
            title="IMPACT · DIRECTIONAL MELD",
            summary=(
                "These are the exact proposed baseline effects of this "
                "directional Meld."
            ),
        )
    )
    return ImpactSessionPresentation(
        view=view,
        controller=controller,
        report_text=compare_report,
        handoff_available=session.state not in {"APPLIED", "KEPT_REVIEW_ONLY"},
    )


def sever_impact_presentation(session: SeverSession) -> ImpactSessionPresentation:
    """Project one saved Sever result with its exact save mode."""

    view = SeverResolutionWorkbenchAdapter(session).view()
    self_save = session.save_mode == "SELF_SAVE"
    summary = "This is the exact local result " + (
        "recorded as saved. "
        if session.state == "APPLIED"
        else "that Apply would save. "
    ) + (
        "It replaces the Source Context."
        if self_save
        else "The Source Context remains unchanged."
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
            f"Enter to open the owning {operation} workflow; this choice does "
            "not apply anything yet."
        ),
    )


def render_impact_session_snapshot(
    presentation: ImpactSessionPresentation,
) -> str:
    """Render the Impact ledger and its available owning-operation route."""

    if presentation.report_text:
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
    return (
        f"{rendered}\n\nTO DO\n"
        f"[ {handoff.kind} ]  {handoff.label} · {handoff.detail}"
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
            "Run the same 'mem impact OPERATION' command outside a TTY for "
            "a snapshot."
        ),
        split_viewer_items=True,
        split_report_text=presentation.report_text or None,
        read_only=True,
        read_only_handoff=(
            _apply_handoff(presentation)
            if presentation.handoff_available
            else None
        ),
        impact_controller=presentation.visible_impact_controller,
    )
    if action.kind == "HANDOFF" and presentation.handoff_available:
        return True
    if action.kind == "CLOSE":
        return False
    # Impact itself has no mutation action. Only the explicit handoff above
    # may leave this surface, and the owning workflow must revalidate again.
    raise ValueError("A standalone Impact view returned an invalid action.")
