"""Context-sensitive keyboard guidance for the Resolution Session."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from prompt_toolkit.application.current import get_app

from memcommit.adapters.console.terminal.components.semantic_viewer import (
    SemanticViewerController,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.application.capabilities.reviewing.session_navigation import (
    WorkbenchSection,
)

from memcommit.adapters.console.terminal.components.resolution.session_shell.controller import (
    ResolutionSessionController,
)


@dataclass(frozen=True)
class ResolutionKeyboardHintState:
    """Live state needed to describe the currently available interaction."""

    controller: ResolutionSessionController
    split_viewer_items: bool
    read_only: bool
    review_and_apply: bool
    toggle_sort_available: bool
    split_kind: Callable[[], str]
    destination_tree_is_focused: Callable[[], bool]
    focused_impact_entry_uid: Callable[[], str | None]
    active_viewer_sections: Callable[[], tuple[WorkbenchSection, ...]]
    viewer_section_index: Callable[[], int]
    viewer_controller: SemanticViewerController
    input_area: Any
    destination_input: Any
    body_control: Any


def resolution_keyboard_hint_text(context: ResolutionKeyboardHintState) -> str:
    """Project available keyboard interactions without owning transitions."""

    controller = context.controller
    active_view = controller.current_view()
    item = controller.navigation.current_item(active_view)
    if get_app().layout.has_focus(context.destination_input):
        navigation_help = (
            " ↑/Tab browse parents  Enter save exact location  Esc cancel "
        )
    elif context.destination_tree_is_focused():
        navigation_help = (
            " ↑/↓ parent  ←/→ expand  Enter use  Tab edit directly  "
            "Esc/Backspace cancel "
        )
    elif context.split_viewer_items and context.split_kind() == "SAVE_LOCATION":
        navigation_help = " Enter change location  Tab switch  Q close "
    elif context.split_viewer_items and context.split_kind() == "RESPONSES":
        if context.read_only:
            navigation_help = " ↑/↓ saved response  Tab switch  Esc/Backspace report "
        elif controller.response_state.option_navigation_active:
            navigation_help = (
                " ↑/↓ choice/Response  Enter select  Esc/Backspace report  Tab switch "
            )
        else:
            navigation_help = (
                " ↑/↓ choice/Response  Enter write response  Tab switch  "
                "Esc/Backspace report "
            )
    elif context.split_viewer_items and context.split_kind() == "REPORT":
        if context.focused_impact_entry_uid() is not None:
            navigation_help = (
                " ↑/↓ Memory  → show  ← hide  Enter toggle  "
                "Tab switch  Esc/Backspace close "
            )
        else:
            navigation_help = (
                " ↑/↓ block (hold accelerates)  PgUp/PgDn page  End last  Tab switch  "
                "Enter inspect  Esc/Backspace close "
                if context.read_only
                else " ↑/↓ block (hold accelerates)  PgUp/PgDn page  End last  Tab switch  "
                "Enter open  Esc/Backspace/Q close "
            )
    elif context.split_viewer_items and context.split_kind() == "TODO":
        todo = controller.displayed_todo()
        if controller.report_apply:
            navigation_help = " Enter apply  Tab switch  Esc cancel "
        elif controller.viewer_content["kind"] == "REVIEW":
            final_action = controller.review_action()
            navigation_help = (
                f" Enter {final_action.kind.lower()}  "
                "Tab inspect review  Esc/Backspace return "
            )
        else:
            todo_hint = (
                "apply confirmation"
                if todo.kind == "REVIEW AND APPLY"
                else todo.kind.lower()
            )
            navigation_help = (
                " Tab switch  Q close "
                if todo.kind == "COMPLETE"
                else f" Enter {todo_hint}  Tab switch  Esc/Backspace back "
            )
    elif context.split_viewer_items and context.split_kind() == "RESOLVE_ALL":
        if controller.viewer_content["kind"] == "REVIEW":
            final_action = controller.review_action()
            review_section = context.active_viewer_sections()[
                context.viewer_section_index()
            ]
            enter_hint = (
                "Enter return"
                if review_section.kind == "SUMMARY"
                else f"Enter {final_action.kind.lower()}"
                if review_section.kind == "ACTION"
                else "←/→ policy"
            )
            navigation_help = (
                f" ↑/↓ review  Tab switch  {enter_hint}  Esc/Backspace return "
            )
        else:
            navigation_help = (
                " ↑/↓ section/item  Tab switch  ←/→ strategy  "
                "Enter open/run  C custom  Esc/Backspace report "
            )
    elif context.viewer_controller.nested_uid is not None:
        navigation_help = " ↑/↓ scroll Memory  Enter/Esc/Backspace back  Tab switch "
    elif (
        context.split_viewer_items
        and controller.viewer_content["kind"] == "ITEM"
        and controller.session_navigation.pane == "viewer"
        and context.active_viewer_sections()[context.viewer_section_index()].kind
        == "SOURCE_MEMORY"
    ):
        navigation_help = (
            " Enter read Memory  ↑/↓ section  Esc/Backspace back  Tab switch "
        )
    elif (
        context.split_viewer_items
        and controller.viewer_content["kind"] == "ITEM"
        and controller.session_navigation.pane == "viewer"
        and context.active_viewer_sections()[context.viewer_section_index()].kind
        == "MEMORY_ROW"
    ):
        navigation_help = (
            " Enter show/hide evidence  ↑/↓ Memory  Esc/Backspace back  Tab switch "
        )
    elif context.split_viewer_items and context.read_only:
        navigation_help = (
            " ↑/↓ section/item  Tab switch  Enter inspect  Esc/Backspace report "
        )
    elif context.split_viewer_items:
        navigation_help = (
            " ↑/↓ section  Tab Responses/Items  C response/comment  "
            "Esc/Backspace report "
        )
    elif (
        item is not None
        and controller.navigation.expanded_item_uid == item.uid
        and item.options
    ):
        navigation_help = (
            " ↑/↓ option  Enter choose/clear  Esc/Backspace back  Tab comment "
        )
    elif controller.navigation.expanded_item_uid is not None:
        navigation_help = " Enter close  Esc/Backspace back  Tab comment "
    else:
        navigation_help = (
            " ↑/↓ item  Enter detail  Shift-Tab switch  Tab/C comment "
            if context.split_viewer_items
            else " ↑/↓ item  Enter detail  Tab comment "
        )

    actions: list[str] = []
    if "SUBMIT_ALL" in active_view.capabilities:
        actions.append("G comment all")
    if "PRESERVE_ALL" in active_view.capabilities:
        actions.append("P preserve all")
    if "DEFER" in active_view.capabilities:
        actions.append("D defer")
    if "ACCEPT" in active_view.capabilities:
        actions.append(
            "A review & apply"
            if context.review_and_apply
            else "A apply"
            if controller.report_apply
            else "A accept"
        )
    if context.toggle_sort_available:
        actions.append("S sort")
    if not (
        get_app().layout.has_focus(context.input_area)
        or get_app().layout.has_focus(context.destination_input)
    ):
        actions.append("H Help")
    if get_app().layout.has_focus(context.body_control):
        actions.append("y/Y copy")
    actions.append("Q close")
    state_label = (
        f" READ ONLY · {safe_terminal_text(active_view.status)} ·"
        if context.read_only
        else ""
    )
    return state_label + navigation_help + "  ".join(actions) + " "
