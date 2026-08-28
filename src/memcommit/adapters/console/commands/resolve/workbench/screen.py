"""Resolve-specific interactive composition over shared terminal surfaces."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.adapters.console.commands.resolve.workbench.presentation import (
    compact_resolve_view,
    project_resolve_analysis,
)
from memcommit.adapters.console.tui.components.plain_text_clipboard import ClipboardWriter
from memcommit.adapters.interfaces.tui.viewers.semantic import run_semantic_viewer
from memcommit.adapters.interfaces.tui.workbenches.resolution.compact_shell import (
    run_compact_resolution_decisions,
)
from memcommit.application.operations.resolve.application import (
    ResolveAnalysis,
    ResolveReceipt,
)
from memcommit.application.resolution.workbench import ResolutionWorkbenchAction


def run_resolve_tui(
    analysis: ResolveAnalysis,
    *,
    apply_candidate: Callable[[str], ResolveReceipt],
    clipboard_writer: ClipboardWriter | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> ResolveReceipt | None:
    """Inspect a terminal outcome or approve one verified plan compactly."""

    if not isinstance(analysis, ResolveAnalysis):
        raise TypeError("Resolve TUI requires a typed analysis.")
    if not analysis.candidates or analysis.status == "ASSUMED":
        run_semantic_viewer(
            project_resolve_analysis(analysis),
            title="RESOLVE · OUTCOME",
            clipboard_writer=clipboard_writer,
            app_input=app_input,
            app_output=app_output,
            require_tty=require_tty,
        )
        return None
    candidate = analysis.candidates[0]
    selected = {"value": candidate.uid}

    def stage(_item_uid: str, option_uid: str) -> None:
        if option_uid != candidate.uid:
            raise ValueError("Resolve selected an unavailable verified plan.")
        selected["value"] = option_uid

    def continue_action(item_uid: str | None) -> ResolutionWorkbenchAction | None:
        if item_uid != "resolve-plan" or selected["value"] != candidate.uid:
            return None
        return ResolutionWorkbenchAction(
            kind="ACCEPT",
            item_uid=item_uid,
            option_uid=candidate.uid,
        )

    action = run_compact_resolution_decisions(
        compact_resolve_view(analysis),
        selected_option=lambda _item_uid: selected["value"],
        stage_option=stage,
        build_continue_action=continue_action,
        continue_label=lambda: "Apply verified plan",
        app_input=app_input,
        app_output=app_output,
    )
    if action.kind == "CLOSE":
        return None
    if action.kind != "ACCEPT" or action.option_uid != candidate.uid:
        raise ValueError("Resolve compact decisions returned an invalid action.")
    return apply_candidate(candidate.uid)


__all__ = ["run_resolve_tui"]
