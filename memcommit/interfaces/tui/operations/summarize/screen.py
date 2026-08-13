"""Interactive read-only presentation for one completed Summarize result."""

from __future__ import annotations

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.interfaces.tui.operations.summarize.adapter import (
    project_summarize_result,
)
from memcommit.interfaces.tui.viewers.semantic import SemanticViewerDocument
from memcommit.interfaces.tui.viewers.semantic.shell import run_semantic_viewer
from memcommit.summarize_application import SummarizeResult


def run_summarize_tui(
    result: SummarizeResult,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> SemanticViewerDocument:
    """Show the typed result without calling a provider or changing state."""

    document = project_summarize_result(result)
    return run_semantic_viewer(
        document,
        title="SUMMARY",
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
