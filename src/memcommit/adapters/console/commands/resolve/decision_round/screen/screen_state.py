"""Process-local issue cursor and operation-supplied selection callbacks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from memcommit.adapters.console.terminal.components.selection import (
    FlatSelectionState,
    SelectionOption,
)
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionItem,
    ResolutionOption,
    ResolutionWorkbenchView,
)


def _recommended(option_uid: str, label: str) -> bool:
    """Mark only an operation-authored recommendation; never infer one."""

    token = label.casefold().strip()
    return option_uid.rpartition(":")[2].casefold() == "recommended" or token in {
        "recommended",
        "recommendation",
    }


@dataclass
class DecisionScreenState:
    """Track the issue list and screen cursor; decisions remain in the caller."""

    supplier: Callable[[], ResolutionWorkbenchView]
    selected_option: Callable[[str], str | None]
    stage_option: Callable[[str, str], None]
    continue_label: Callable[[], str]
    bulk_options: tuple[ResolutionOption, ...] = ()
    show_item_navigation: bool = False
    require_all_decisions: bool = True
    items: tuple[ResolutionItem, ...] = field(init=False)
    current_issue_index: int = field(default=0, init=False)
    focused_row_index: int = field(default=0, init=False)
    status_message: str = field(default="", init=False)
    navigation: FlatSelectionState = field(init=False)

    def __post_init__(self) -> None:
        self.items = tuple(
            item
            for item in self.supplier().items
            if item.effective_obligation in {"REQUIRED", "OPTIONAL"}
            and item.response_state != "NOT_APPLICABLE"
        )
        self.navigation = FlatSelectionState(
            (SelectionOption("PREV", "← PREV"), SelectionOption("NEXT", "NEXT →")),
            cursor_uid="PREV",
        )

    @property
    def navigation_visible(self) -> bool:
        return self.show_item_navigation and len(self.items) > 1

    def initialize_selection(self) -> None:
        # Only explicit recommendations may become defaults. Constructing the
        # state alone must not stage operation decisions for a custom screen.
        for item in self.items:
            if self.selected_option(item.uid) is not None or item.selected_option_uid:
                continue
            recommendations = tuple(
                option
                for option in item.options
                if _recommended(option.uid, option.label)
            )
            if len(recommendations) == 1:
                self.stage_option(item.uid, recommendations[0].uid)
        if self.items:
            self.current_issue_index = next(
                (
                    index
                    for index, item in enumerate(self.items)
                    if self.selected_option(item.uid) is not None
                ),
                0,
            )
        self.focus_selected_choice()

    def current_issue(self) -> ResolutionItem | None:
        return self.items[self.current_issue_index] if self.items else None

    def selected_for(self, item: ResolutionItem) -> str | None:
        return self.selected_option(item.uid) or item.selected_option_uid

    def focus_selected_choice(self) -> None:
        item = self.current_issue()
        if item is None:
            self.focused_row_index = 0
            return
        selected_uid = self.selected_for(item)
        self.focused_row_index = next(
            (
                index
                for index, option in enumerate(item.options)
                if option.uid == selected_uid
            ),
            0,
        )

    def action_rows(
        self, *, response_available: bool = False
    ) -> tuple[SelectionOption, ...]:
        rows = (
            [SelectionOption("action:RESPONSE", "Direction or note")]
            if response_available
            else []
        )
        rows.extend(
            SelectionOption(f"bulk:{option.uid}", option.label)
            for option in self.bulk_options
        )
        rows.append(SelectionOption("action:CONTINUE", self.continue_label()))
        return tuple(rows)

    def row_count(self, *, response_available: bool = False) -> int:
        item = self.current_issue()
        return (len(item.options) if item is not None else 0) + len(
            self.action_rows(response_available=response_available)
        )
