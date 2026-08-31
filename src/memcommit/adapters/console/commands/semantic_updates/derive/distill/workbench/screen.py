"""Distill adapter over the shared Context semantic-result workbench."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.adapters.console.commands.semantic_updates.derive.distill.workbench.model import DistillTuiSetup
from memcommit.adapters.console.commands.semantic_updates.derive.distill.workbench.presentation import (
    project_distill_clipboard,
    project_distill_result,
)
from memcommit.adapters.console.terminal.core.capabilities import require_interactive_terminal
from memcommit.adapters.console.terminal.components.context_summary import (
    ContextSummaryWorkbenchView,
    run_context_summary_workbench,
)
from memcommit.application.operations.semantic_updates.derive.distill.application import DistillRequest, DistillResult


def run_distill_tui(
    request: DistillRequest,
    *,
    setup: DistillTuiSetup,
    execute: Callable[[DistillRequest], DistillResult],
    clipboard_writer: Callable[[str], None] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> DistillResult | None:
    """Choose one Source reach, run explicitly, and inspect the exact proposal."""

    if require_tty:
        require_interactive_terminal("Interactive Distill")
    if not isinstance(request, DistillRequest):
        raise TypeError("Distill TUI requires a DistillRequest.")
    if not isinstance(setup, DistillTuiSetup):
        raise TypeError("Distill TUI requires a frozen setup catalog.")
    if request.include_descendants != request.follow_embeds:
        raise ValueError("Distill TUI requires the DIRECT or RECURSIVE preset.")

    current_request = DistillRequest(
        context_locator=request.context_locator or setup.selected_context,
        goal=request.goal,
        include_descendants=request.include_descendants,
        follow_embeds=request.follow_embeds,
    )
    range_mode = setup.initial_range_mode
    result: DistillResult | None = None
    while True:
        context_name = current_request.context_locator
        if context_name is None or context_name not in setup.names:
            raise ValueError(
                "The selected Distill Context is no longer available. "
                "Reopen Distill and select it again."
            )

        def clipboard_projector(
            focused_uid: str | None,
            whole_document: bool,
        ) -> tuple[str, str]:
            if result is None:
                raise ValueError("Run Distill before copying its proposal.")
            projection = project_distill_clipboard(
                result,
                focused_uid=focused_uid,
                whole_document=whole_document,
            )
            return projection.text, projection.label

        receipt = run_context_summary_workbench(
            ContextSummaryWorkbenchView(
                names=setup.names,
                selected_context=context_name,
                range_mode=range_mode,
                operation_label="DISTILL",
                result_title="RULE PROPOSAL",
                empty_message=(
                    "Run Distill against the exact Ground working-candidate frame.\n"
                    " The Ground Goal focuses relevance only."
                    if setup.source_locked
                    else "Choose a Source Context and descendants range, then run Distill.\n"
                    " The optional Goal supplied by the caller focuses relevance only."
                ),
                current_context=setup.current_context,
                annotations=setup.annotations,
                document=None if result is None else project_distill_result(result),
                allow_both=False,
                targeting_editable=not setup.source_locked,
                memory_loader=setup.memory_loader,
            ),
            clipboard_projector=None if result is None else clipboard_projector,
            clipboard_writer=clipboard_writer,
            app_input=app_input,
            app_output=app_output,
            require_tty=False,
        )
        if receipt is None:
            return result
        range_mode = receipt.range_mode
        include_descendants = range_mode == "SUBTREE"
        current_request = DistillRequest(
            context_locator=receipt.context_name,
            goal=request.goal,
            include_descendants=include_descendants,
            follow_embeds=include_descendants,
        )
        result = execute(current_request)
        if not isinstance(result, DistillResult):
            raise TypeError("Distill execution returned an invalid result.")
