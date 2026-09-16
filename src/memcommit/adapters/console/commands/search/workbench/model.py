"""Process-local Search workbench results, selection, and save eligibility."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from memcommit.adapters.console.terminal.components.selection import (
    FlatMultiSelectionState,
    SelectionOption,
)
from memcommit.adapters.console.terminal.components.plain_text_clipboard import (
    PlainTextClipboardReceipt,
)
from memcommit.application.operations.search.application import (
    SearchRequest,
    SearchResponse,
)
from memcommit.application.capabilities.save_context_from_selection.application import (
    SaveContextMode,
)


@dataclass(frozen=True)
class SearchResultsClipboardProjection:
    """One focused Search result or the complete frozen ranked result set."""

    text: str
    scope: Literal["FOCUSED", "RESULT_SET"]
    label: str
    result_count: int


@dataclass(frozen=True)
class SearchWorkbenchResult:
    """Close state or one reviewed Save request."""

    status: Literal["CLOSED", "SAVE"]
    response: SearchResponse | None = None
    selected_result_indices: tuple[int, ...] = ()
    save_as: SaveContextMode | None = None
    save_location: str | None = None

    def __post_init__(self) -> None:
        if self.status == "CLOSED":
            if (
                self.selected_result_indices
                or self.save_as is not None
                or self.save_location is not None
            ):
                raise ValueError("A closed Search workbench cannot request a save.")
            return
        if (
            self.response is None
            or not self.selected_result_indices
            or self.save_as not in {"COPY", "REFERENCE", "EMBED"}
            or not isinstance(self.save_location, str)
            or not self.save_location.strip()
        ):
            raise ValueError("Search Save As requires reviewed result choices.")
        if len(set(self.selected_result_indices)) != len(
            self.selected_result_indices
        ) or any(
            isinstance(index, bool)
            or not isinstance(index, int)
            or not 0 <= index < len(self.response.results)
            for index in self.selected_result_indices
        ):
            raise ValueError("Search Save As selected invalid result rows.")


SearchRunner = Callable[[SearchRequest], SearchResponse]
SearchSaveLocationValidator = Callable[[str], object]


def search_save_location_stem(context_name: str, query: str) -> str:
    """Build one editable local name suggestion without assigning identity."""

    words = "-".join(query.strip().split()) or "search"
    safe = "".join(
        "-" if character in "/\\:" or ord(character) < 32 else character
        for character in words
    ).strip("-.")
    if not safe:
        safe = "search"
    if len(safe) > 48:
        safe = safe[:48].rstrip("-.") or "search"
    return f"{context_name}/results/{safe}"


def search_save_as_available(response: SearchResponse | None, *, busy: bool) -> bool:
    return not busy and response is not None and bool(response.results)


@dataclass
class SearchWorkbenchState:
    """Own result invalidation and eligibility; shared selectors own navigation."""

    response: SearchResponse | None = None
    result_selection: FlatMultiSelectionState | None = None
    status: str = "ENTER A QUERY"
    copy_receipt: PlainTextClipboardReceipt | None = None
    save_location_edited: bool = False
    setting_save_location: bool = False

    def clear_results(self, message: str) -> None:
        # A result set and its checked indices describe one exact request.
        # Changing query or scope invalidates both, including clipboard feedback.
        self.response = None
        self.result_selection = None
        self.copy_receipt = None
        self.status = message

    def accept_response(
        self,
        response: SearchResponse,
        options: tuple[SelectionOption, ...],
    ) -> None:
        self.response = response
        self.copy_receipt = None
        self.result_selection = (
            FlatMultiSelectionState(options, cursor_uid="0")
            if response.results
            else None
        )
        count = len(response.results)
        self.status = f"{count} {'RESULT' if count == 1 else 'RESULTS'}"

    def selected_save_indices(self) -> tuple[int, ...]:
        if self.response is None or self.result_selection is None:
            raise ValueError("RUN SEARCH AND CHECK AT LEAST ONE RESULT")
        indices = tuple(int(uid) for uid in self.result_selection.selected_uids)
        if not indices:
            raise ValueError("CHECK AT LEAST ONE RESULT")
        selected_results = tuple(self.response.results[index] for index in indices)
        unsupported = next(
            (
                result.kind
                for result in selected_results
                if result.kind not in {"memory", "ref"}
            ),
            None,
        )
        if unsupported is not None:
            raise ValueError(f"{unsupported.upper()} RESULTS CANNOT BE SAVED")
        if any(result.source_memory_uid is None for result in selected_results):
            raise ValueError("A CHECKED RESULT HAS NO SOURCE MEMORY IDENTITY")
        return indices


def validate_search_response(
    request: SearchRequest, response: SearchResponse
) -> SearchResponse:
    if not isinstance(response, SearchResponse):
        raise ValueError("Search controller returned an invalid response.")
    if response.request != request:
        raise ValueError(
            "Search inputs changed while the request was running. Run the search again."
        )
    return response
