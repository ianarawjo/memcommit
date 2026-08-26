"""Summarize adapter over the shared Context-result workbench."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.interfaces.console.terminal import require_interactive_terminal
from memcommit.interfaces.tui.operations.summarize.adapter import (
    project_summarize_clipboard,
    project_summarize_outcome,
)
from memcommit.interfaces.tui.operations.summarize.model import (
    SummarizeTuiOutcome,
    SummarizeTuiSetup,
)
from memcommit.interfaces.tui.workbenches.context_summary import (
    ContextSummaryWorkbenchView,
    run_context_summary_workbench,
)
from memcommit.operations.summarize.application import SummarizeRequest, SummarizeResult


def run_summarize_tui(
    request: SummarizeRequest,
    *,
    setup: SummarizeTuiSetup,
    execute: Callable[[SummarizeRequest], SummarizeResult],
    clipboard_writer: Callable[[str], None] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> SummarizeTuiOutcome | None:
    """Select one readable scope, execute explicitly, and inspect its result."""

    if require_tty:
        require_interactive_terminal("Interactive Summarize")
    if not isinstance(request, SummarizeRequest):
        raise TypeError("Summarize TUI requires a SummarizeRequest.")
    if not isinstance(setup, SummarizeTuiSetup):
        raise TypeError("Summarize TUI requires a frozen setup catalog.")
    if request.include_descendants != request.follow_embeds:
        raise ValueError(
            "Summarize TUI requires the shared DIRECT or RECURSIVE range preset."
        )

    current_request = SummarizeRequest(
        context_locator=request.context_locator or setup.selected_context,
        include_descendants=request.include_descendants,
        follow_embeds=request.follow_embeds,
    )
    range_mode = setup.initial_range_mode
    outcome: SummarizeTuiOutcome | None = None
    while True:
        context_name = current_request.context_locator
        if context_name is None or context_name not in setup.names:
            raise ValueError(
                "The selected Summarize Context is no longer available. "
                "Reopen Summarize and select it again."
            )

        def project_clipboard(
            focused_uid: str | None,
            whole_document: bool,
        ) -> tuple[str, str]:
            if outcome is None:
                raise ValueError("Run Summarize before copying its result.")
            projection = project_summarize_clipboard(
                outcome,
                focused_uid=focused_uid,
                whole_document=whole_document,
            )
            return projection.text, projection.label

        receipt = run_context_summary_workbench(
            ContextSummaryWorkbenchView(
                names=setup.names,
                selected_context=context_name,
                range_mode=range_mode,
                operation_label="SUMMARIZE",
                result_title="SUMMARY",
                empty_message=(
                    "Choose a Context and descendants range, then run Summarize.\n"
                    " No provider or summary execution has occurred."
                ),
                current_context=setup.current_context,
                annotations=setup.annotations,
                document=(
                    None if outcome is None else project_summarize_outcome(outcome)
                ),
                memory_loader=setup.memory_loader,
            ),
            clipboard_projector=(None if outcome is None else project_clipboard),
            clipboard_writer=clipboard_writer,
            app_input=app_input,
            app_output=app_output,
            require_tty=False,
        )
        if receipt is None:
            return outcome
        range_mode = receipt.range_mode
        reaches = (
            (False, True)
            if range_mode == "BOTH"
            else (range_mode == "SUBTREE",)
        )
        requests = tuple(
            SummarizeRequest(
                context_locator=receipt.context_name,
                include_descendants=include_descendants,
                follow_embeds=include_descendants,
            )
            for include_descendants in reaches
        )
        results = tuple(execute(next_request) for next_request in requests)
        if any(not isinstance(result, SummarizeResult) for result in results):
            raise TypeError("Summarize execution returned an invalid result.")
        current_request = requests[-1]
        outcome = SummarizeTuiOutcome(results)
