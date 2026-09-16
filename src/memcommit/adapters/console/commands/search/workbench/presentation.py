"""Search screen labels, result fragments, footer, and plain-text clipboard projection."""

from __future__ import annotations

from collections.abc import Mapping

from memcommit.adapters.console.commands.search.receipt import (
    SearchResultViewRow,
    render_grouped_search_results,
)
from memcommit.adapters.console.commands.search.workbench.model import (
    SearchResultsClipboardProjection,
    SearchWorkbenchState,
)
from memcommit.adapters.console.terminal.components.background_turn import (
    BackgroundExecutorTurn,
)
from memcommit.adapters.console.terminal.components.progress import busy_suffix
from memcommit.adapters.console.terminal.components.selection import SelectionOption
from memcommit.adapters.console.terminal.components.selection.multiple import (
    render_vertical_multi_choice_rows,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.application.operations.search.application import (
    SearchResponse,
    SearchResult,
)
from memcommit.source_projection.model import SourceForm
from memcommit.source_projection.presentation import (
    SourceDisplayValue,
    source_display_text,
    source_object_label,
)


_RESULT_SOURCE_FORMS = {
    "memory": SourceForm.MEMORY,
    "ref": SourceForm.MEMORY_REF,
    "query": SourceForm.QUERY_VIEW,
}


def _search_result_kind_label(result: "SearchResult") -> str:
    form = _RESULT_SOURCE_FORMS.get(result.kind)
    return (
        source_object_label(form)
        if form is not None
        else result.kind.replace("_", " ").upper()
    )


def _search_result_annotation(result: "SearchResult") -> str:
    return "RELATED" if result.relevance == "related" else ""


def search_result_selection_label(
    result: "SearchResult",
    *,
    number: int,
    context_annotation: SourceDisplayValue | None = None,
) -> str:
    """Project one complete selectable Search result as one logical row."""

    location = [result.context_name]
    annotation = source_display_text(context_annotation)
    if annotation:
        location.append(annotation)
    location.append(_search_result_kind_label(result).upper())
    related = _search_result_annotation(result)
    if related:
        location.append(related)
    content = " ".join(result.content.split())
    return f"{number} [{result.uid[:8]}] {content} [{' · '.join(location)}]"


def _search_result_view_row(
    result: SearchResult,
    *,
    rank: int,
) -> SearchResultViewRow:
    return SearchResultViewRow(
        context_name=result.context_name,
        label=(
            f"[{rank} {_search_result_kind_label(result)} {result.uid[:8]}]"
            + (
                f" · {_search_result_annotation(result)}"
                if _search_result_annotation(result)
                else ""
            )
        ),
        content=result.content,
    )


def render_search_results(response: SearchResponse | None) -> str:
    """Render only rows whose request still matches the visible controls."""

    if response is None:
        return "SEARCH RESULTS\n  Enter a query to search the selected scope."
    rows = tuple(
        _search_result_view_row(result, rank=index)
        for index, result in enumerate(response.results, start=1)
    )
    return render_grouped_search_results(
        rows,
        related_query=response.related_query,
    )


def project_search_results_clipboard(
    response: SearchResponse | None,
    *,
    focused_index: int = 0,
    whole_result_set: bool = False,
) -> SearchResultsClipboardProjection:
    """Project host-resolved results without checkbox or viewport wrapping."""

    if response is None or not response.results:
        raise ValueError("There are no Search results to copy.")
    count = len(response.results)
    if whole_result_set:
        suffix = "Result" if count == 1 else "Results"
        return SearchResultsClipboardProjection(
            text=render_search_results(response),
            scope="RESULT_SET",
            label=f"complete Search result set · {count} {suffix}",
            result_count=count,
        )
    if isinstance(focused_index, bool) or not 0 <= focused_index < count:
        raise ValueError("The focused Search result is no longer available.")
    result = response.results[focused_index]
    return SearchResultsClipboardProjection(
        text=render_grouped_search_results(
            (
                _search_result_view_row(
                    result,
                    rank=focused_index + 1,
                ),
            ),
            related_query=response.related_query,
        ),
        scope="FOCUSED",
        label=(
            f"Search result {focused_index + 1} · "
            f"{safe_terminal_text(result.context_name)} · "
            f"{safe_terminal_text(_search_result_kind_label(result))}"
        ),
        result_count=1,
    )


def results_frame_title(turn: BackgroundExecutorTurn[SearchResponse]) -> str:
    if turn.busy:
        return f"RESULTS · SEARCHING {busy_suffix(turn.frame)}"
    return "RESULTS"


def result_selection_options(
    response: SearchResponse,
    labels: Mapping[str, SourceDisplayValue],
) -> tuple[SelectionOption, ...]:
    return tuple(
        SelectionOption(
            str(index),
            search_result_selection_label(
                result,
                number=index + 1,
                context_annotation=labels.get(result.context_name),
            ),
        )
        for index, result in enumerate(response.results)
    )


def render_result_fragments(
    state: SearchWorkbenchState, *, focused: bool, columns: int
) -> list[tuple[str, str]]:
    if state.response is None or state.result_selection is None:
        return [("", "Enter a query to search the selected scope.")]
    if not state.response.results:
        return [("", "(no matching items)")]
    fragments: list[tuple[str, str]] = []
    if state.response.related_query:
        fragments.extend(
            [
                ("class:heading", "RELATED RESULTS\n"),
                (
                    "",
                    f"Broader search: {safe_terminal_text(state.response.related_query)}\n\n",
                ),
            ]
        )
    # Search now follows the service-wide one-column session grammar. Result
    # rows therefore own the full frame width instead of retaining the
    # former side-by-side Save As allowance.
    width = max(24, columns - 6)
    fragments.extend(
        render_vertical_multi_choice_rows(
            state.result_selection,
            focused=focused,
            content_width=width,
            numbered=False,
        )
    )
    return fragments


def render_footer(
    state: SearchWorkbenchState,
    turn: BackgroundExecutorTurn[SearchResponse],
    *,
    search_focused: bool,
    results_focused: bool,
) -> str | list[tuple[str, str]]:
    if turn.busy:
        return f" SEARCHING {busy_suffix(turn.frame)} · Ctrl-C closes after search"
    hint = (
        "Enter search · Tab/Shift-Tab panes · Esc/Ctrl-C close"
        if search_focused
        else (
            "↑/↓ move/cross · Enter activate/check · ←/→ adjust · "
            "/ search · Esc back · H Help · Q close"
        )
    )
    if results_focused:
        hint = (
            "↑/↓ move results · Enter/Space check · y copy focused · "
            "Y copy all results · / search · Esc back"
        )
    if state.copy_receipt is not None and results_focused:
        return [
            (state.copy_receipt.style, " " + state.copy_receipt.message),
            ("", f" · {hint}"),
        ]
    return f" {safe_terminal_text(state.status)} · {hint}"
