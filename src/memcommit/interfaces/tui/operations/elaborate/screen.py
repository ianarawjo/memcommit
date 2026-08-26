"""Standalone Elaborate adapter over the shared semantic Viewer."""

from __future__ import annotations

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.operations.elaborate.application import ElaborateResult
from memcommit.interfaces.tui.components.plain_text_clipboard import ClipboardWriter
from memcommit.interfaces.tui.operations.elaborate.adapter import (
    project_elaborate_clipboard,
    project_elaborate_result,
)
from memcommit.interfaces.tui.viewers.semantic import run_semantic_viewer


def run_elaborate_tui(
    result: ElaborateResult,
    *,
    clipboard_writer: ClipboardWriter | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> ElaborateResult:
    if not isinstance(result, ElaborateResult):
        raise TypeError("Elaborate TUI requires a typed result.")

    def clipboard_projector(
        focused_uid: str | None,
        whole_document: bool,
    ) -> tuple[str, str]:
        projection = project_elaborate_clipboard(
            result,
            focused_uid=focused_uid,
            whole_document=whole_document,
        )
        return projection.text, projection.label

    run_semantic_viewer(
        project_elaborate_result(result),
        title="ELABORATE",
        clipboard_projector=clipboard_projector,
        clipboard_writer=clipboard_writer,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    return result
