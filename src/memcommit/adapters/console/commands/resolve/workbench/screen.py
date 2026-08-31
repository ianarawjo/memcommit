"""Resolve-owned decision collection over shared terminal mechanics."""

from __future__ import annotations

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.adapters.console.commands.resolve.workbench.presentation import (
    compact_resolve_view,
    project_resolve_analysis,
)
from memcommit.adapters.console.terminal.components.plain_text_clipboard import (
    ClipboardWriter,
)
from memcommit.adapters.console.terminal.components.resolution.compact_shell import (
    run_compact_resolution_decisions,
)
from memcommit.adapters.console.terminal.components.semantic_viewer import (
    run_semantic_viewer,
)
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionWorkbenchAction,
)
from memcommit.application.operations.resolve.application import (
    ResolveAnalysis,
    ResolveError,
)
from memcommit.application.operations.resolve.decisions import (
    ResolveDecision,
)


def run_resolve_tui(
    analysis: ResolveAnalysis,
    *,
    clipboard_writer: ClipboardWriter | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> tuple[ResolveDecision, ...] | None:
    """Collect one explicit decision per Audit item, without applying anything."""

    if not isinstance(analysis, ResolveAnalysis):
        raise TypeError("Resolve TUI requires a typed analysis.")
    if not analysis.review_issues:
        run_semantic_viewer(
            project_resolve_analysis(analysis),
            title="RESOLVE · OUTCOME",
            clipboard_writer=clipboard_writer,
            app_input=app_input,
            app_output=app_output,
            require_tty=require_tty,
        )
        return None

    selected: dict[str, str] = {}
    responses: dict[str, str] = {}
    issue_uids = {issue.uid for issue in analysis.review_issues}

    def stage(item_uid: str, option_uid: str) -> None:
        if item_uid not in issue_uids or option_uid not in {
            f"{item_uid}:confirm",
            f"{item_uid}:intent",
            f"{item_uid}:force",
        }:
            raise ResolveError("Resolve selected an unavailable decision.")
        selected[item_uid] = option_uid

    def stage_response(item_uid: str, value: str) -> None:
        if item_uid not in issue_uids:
            raise ResolveError("Resolve response names an unavailable Audit item.")
        responses[item_uid] = value
        if value.strip():
            selected[item_uid] = f"{item_uid}:intent"

    def validate_response(value: str) -> None:
        if value and not value.strip():
            raise ValueError("YOUR INTENT cannot contain only whitespace.")

    def continue_action(_item_uid: str | None) -> ResolutionWorkbenchAction | None:
        for issue in analysis.review_issues:
            option_uid = selected.get(issue.uid)
            if option_uid is None:
                return None
            if option_uid == f"{issue.uid}:intent" and not responses.get(
                issue.uid, ""
            ).strip():
                return None
        return ResolutionWorkbenchAction(kind="ACCEPT")

    action = run_compact_resolution_decisions(
        compact_resolve_view(analysis),
        selected_option=lambda item_uid: selected.get(item_uid),
        stage_option=stage,
        response_text=lambda item_uid: responses.get(item_uid, ""),
        stage_response=stage_response,
        response_validator=validate_response,
        response_option_uid=lambda item_uid: f"{item_uid}:intent",
        response_title="YOUR INTENT",
        header_label="RESOLVE",
        activation_hint="select/finalize",
        show_item_navigation=True,
        build_continue_action=continue_action,
        continue_label=lambda: "Finalize decisions",
        app_input=app_input,
        app_output=app_output,
    )
    if action.kind == "CLOSE":
        return None
    if action.kind != "ACCEPT":
        raise ResolveError("Resolve decisions returned an invalid action.")

    decisions: list[ResolveDecision] = []
    for issue in analysis.review_issues:
        option_uid = selected[issue.uid]
        suffix = option_uid.rpartition(":")[2]
        if suffix == "confirm":
            decisions.append(ResolveDecision(issue.uid, "CONFIRM"))
        elif suffix == "intent":
            decisions.append(
                ResolveDecision(
                    issue.uid,
                    "INTENT",
                    responses[issue.uid].strip(),
                )
            )
        else:
            decisions.append(ResolveDecision(issue.uid, "FORCE"))
    return tuple(decisions)


__all__ = ["run_resolve_tui"]
