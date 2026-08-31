"""Compact paged inspection for a completed Find request."""

from __future__ import annotations

from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.adapters.console.commands.search_explain.retrieve_answer.find.presentation import (
    DEFAULT_FIND_PREVIEW_MATCHES,
    find_result_header_lines,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.commands.search_explain.retrieve_answer.find.source_row import (
    render_find_reference_row,
)
from memcommit.adapters.console.terminal.components.paged_result import (
    PagedResultRenderer,
    PagedResultState,
    run_paged_result,
)
from memcommit.application.operations.search_explain.retrieve_answer.find.application import FindResult


def run_compact_find_result(
    result: FindResult,
    *,
    all_readable_contexts: bool = False,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> int:
    """Browse one frozen Find result without occupying the alternate screen."""

    if not isinstance(result, FindResult):
        raise TypeError("Compact Find paging requires a FindResult.")
    if not result.matches:
        raise ValueError("Compact Find paging requires at least one match.")

    def header(state: PagedResultState) -> StyleAndTextTuples:
        lines = find_result_header_lines(
            result,
            visible_range=(state.page_start, state.page_stop),
            all_readable_contexts=all_readable_contexts,
        )
        fragments: StyleAndTextTuples = [("class:report-label", lines[0])]
        fragments.extend(("class:report-neutral", "\n" + line) for line in lines[1:])
        return fragments

    def row(index: int) -> StyleAndTextTuples:
        text = safe_terminal_text(
            render_find_reference_row(
                result.matches[index],
                number=index + 1,
            )
        )
        return [("class:report-neutral", text)]

    return run_paged_result(
        PagedResultRenderer(
            item_count=len(result.matches),
            header=header,
            row=row,
            header_height=4,
            page_size=DEFAULT_FIND_PREVIEW_MATCHES,
            row_window_height=DEFAULT_FIND_PREVIEW_MATCHES * 2,
        ),
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )


__all__ = ["run_compact_find_result"]
