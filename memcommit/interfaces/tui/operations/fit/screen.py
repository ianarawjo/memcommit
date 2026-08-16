"""Standalone Fit adapter over the shared semantic Viewer."""

from __future__ import annotations

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.fit_application import FitPropositionsResult, FitResult
from memcommit.interfaces.tui.components.plain_text_clipboard import ClipboardWriter
from memcommit.interfaces.tui.operations.fit.adapter import (
    project_proposition_fit_clipboard,
    project_proposition_fit_result,
    project_fit_clipboard,
    project_fit_result,
)
from memcommit.interfaces.tui.viewers.semantic import run_semantic_viewer


def run_proposition_fit_tui(
    result: FitPropositionsResult,
    *,
    clipboard_writer: ClipboardWriter | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> FitPropositionsResult:
    """Inspect one role-neutral Fit judgment without changing state."""

    if not isinstance(result, FitPropositionsResult):
        raise TypeError("General Fit TUI requires a typed result.")

    def clipboard_projector(
        focused_uid: str | None,
        whole_document: bool,
    ) -> tuple[str, str]:
        projection = project_proposition_fit_clipboard(
            result,
            focused_uid=focused_uid,
            whole_document=whole_document,
        )
        return projection.text, projection.label

    run_semantic_viewer(
        project_proposition_fit_result(result),
        title="FIT",
        clipboard_projector=clipboard_projector,
        clipboard_writer=clipboard_writer,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    return result


def run_fit_tui(
    result: FitResult,
    *,
    clipboard_writer: ClipboardWriter | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> FitResult:
    """Inspect one immutable Fit result without exposing execution actions."""

    if not isinstance(result, FitResult):
        raise TypeError("Fit TUI requires a typed result.")

    def clipboard_projector(
        focused_uid: str | None,
        whole_document: bool,
    ) -> tuple[str, str]:
        projection = project_fit_clipboard(
            result,
            focused_uid=focused_uid,
            whole_document=whole_document,
        )
        return projection.text, projection.label

    run_semantic_viewer(
        project_fit_result(result),
        title="FIT",
        clipboard_projector=clipboard_projector,
        clipboard_writer=clipboard_writer,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    return result
