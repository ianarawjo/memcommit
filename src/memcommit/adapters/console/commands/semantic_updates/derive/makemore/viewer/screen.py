"""Standalone Makemore adapter over the shared semantic Viewer."""

from __future__ import annotations

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.application.operations.semantic_updates.derive.makemore.application import MakemoreResult
from memcommit.adapters.console.terminal.components.plain_text_clipboard import ClipboardWriter
from memcommit.adapters.console.commands.semantic_updates.derive.makemore.viewer.projection import (
    project_makemore_clipboard,
    project_makemore_result,
)
from memcommit.adapters.console.terminal.components.semantic_viewer import run_semantic_viewer


def run_makemore_tui(
    result: MakemoreResult,
    *,
    clipboard_writer: ClipboardWriter | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> MakemoreResult:
    if not isinstance(result, MakemoreResult):
        raise TypeError("Makemore TUI requires a typed result.")

    def clipboard_projector(
        focused_uid: str | None,
        whole_document: bool,
    ) -> tuple[str, str]:
        projection = project_makemore_clipboard(
            result,
            focused_uid=focused_uid,
            whole_document=whole_document,
        )
        return projection.text, projection.label

    run_semantic_viewer(
        project_makemore_result(result),
        title="MAKEMORE",
        clipboard_projector=clipboard_projector,
        clipboard_writer=clipboard_writer,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    return result
