"""Typed Answer projections for the Query terminal interface."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.operations.search.answer_references import (
    SearchAnswerReferenceDocument,
    render_numbered_search_answer_reference,
)
from memcommit.adapters.console.text import safe_terminal_text
from memcommit.adapters.interfaces.tui.core.theme import focused_control_style
from memcommit.application.operations.query.ordinary_application import (
    OrdinaryQueryResponse,
)
from memcommit.source_projection.model import SourceForm
from memcommit.source_projection.presentation import source_object_label
from memcommit.adapters.interfaces.tui.operations.query.model import (
    QueryAnswerClipboardProjection,
    QueryWorkbenchResponse,
)


QUERY_VIEW_LABEL = source_object_label(SourceForm.QUERY_VIEW).upper()


def render_query_answer(response: QueryWorkbenchResponse | None) -> str:
    if response is None:
        return "QUERY ANSWER\n  Enter a question for the selected Source and Scope."
    if isinstance(response, OrdinaryQueryResponse):
        return response.answer
    return response.answer


def query_answer_reference_document(
    response: QueryWorkbenchResponse | None,
) -> SearchAnswerReferenceDocument | None:
    if not isinstance(response, OrdinaryQueryResponse):
        return None
    return response.reference_document


def query_answer_stop_count(response: QueryWorkbenchResponse | None) -> int:
    """Return the answer body plus every independently navigable Reference."""

    document = query_answer_reference_document(response)
    return 1 + (len(document.references) if document is not None else 0)


@dataclass
class QueryAnswerFocus:
    """Process-local cursor over the answer body and typed Reference blocks."""

    stop_index: int = 0

    def reset(self) -> None:
        self.stop_index = 0

    def move(self, response: QueryWorkbenchResponse | None, delta: int) -> bool:
        if delta not in {-1, 1}:
            raise ValueError("Query Answer focus direction must be -1 or 1.")
        last = query_answer_stop_count(response) - 1
        next_index = max(0, min(self.stop_index + delta, last))
        if next_index == self.stop_index:
            return False
        self.stop_index = next_index
        return True

    def enter(
        self,
        response: QueryWorkbenchResponse | None,
        delta: int,
    ) -> None:
        self.stop_index = 0 if delta > 0 else query_answer_stop_count(response) - 1


def project_query_answer_clipboard(
    response: QueryWorkbenchResponse | None,
    *,
    focus: QueryAnswerFocus,
    whole_document: bool = False,
) -> QueryAnswerClipboardProjection:
    """Project typed Answer focus without parsing or terminal wrapping."""
    if response is None:
        raise ValueError("There is no Query answer to copy.")

    document = query_answer_reference_document(response)
    if document is None:
        return QueryAnswerClipboardProjection(
            text=safe_terminal_text(render_query_answer(response)),
            scope="DOCUMENT" if whole_document else "FOCUSED",
            label="complete answer" if whole_document else "answer",
        )

    reference_count = len(document.references)
    if whole_document:
        suffix = "Reference" if reference_count == 1 else "References"
        return QueryAnswerClipboardProjection(
            text=safe_terminal_text(document.text),
            scope="DOCUMENT",
            label=f"complete answer · {reference_count} {suffix}",
            reference_count=reference_count,
        )

    active_stop = max(0, min(focus.stop_index, reference_count))
    if active_stop == 0:
        return QueryAnswerClipboardProjection(
            text=safe_terminal_text(document.body),
            scope="FOCUSED",
            label="answer body",
            reference_count=reference_count,
        )
    reference = document.references[active_stop - 1]
    return QueryAnswerClipboardProjection(
        text=safe_terminal_text(render_numbered_search_answer_reference(reference)),
        scope="FOCUSED",
        label=f"Reference {reference.number}",
        reference_count=reference_count,
    )


def render_query_answer_fragments(
    response: QueryWorkbenchResponse | None,
    *,
    focus: QueryAnswerFocus,
    focused: bool,
) -> list[tuple[str, str]]:
    """Render one Answer with shared blue focus over its active Reference."""

    document = query_answer_reference_document(response)
    if document is None:
        return [("", safe_terminal_text(render_query_answer(response)))]

    active_stop = max(
        0,
        min(focus.stop_index, query_answer_stop_count(response) - 1),
    )
    fragments: list[tuple[str, str]] = []
    if active_stop == 0 and focused:
        fragments.append(("[SetCursorPosition]", ""))
    fragments.extend(
        [
            ("", safe_terminal_text(document.body)),
            ("", "\n\nReferences"),
        ]
    )
    for index, reference in enumerate(document.references, start=1):
        active = active_stop == index
        fragments.append(("", "\n"))
        if active and focused:
            fragments.append(("[SetCursorPosition]", ""))
        fragments.append(
            (
                (
                    focused_control_style(focused=focused, selected=True)
                    if active
                    else ""
                ),
                safe_terminal_text(render_numbered_search_answer_reference(reference)),
            )
        )
    return fragments
