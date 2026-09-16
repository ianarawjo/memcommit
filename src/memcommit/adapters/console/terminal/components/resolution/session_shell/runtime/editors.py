"""Response-draft and Save Location editing for a Resolution Session."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.application.current import get_app

from memcommit.adapters.console.terminal.components.responses.model import ResponseDraft
from memcommit.adapters.console.terminal.components.save_location import (
    SaveLocationEditorState,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text

from memcommit.adapters.console.terminal.components.resolution.session_shell.controller import (
    ResolutionSessionController,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.presentation import (
    ResolutionDestination,
    _item_draft,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.controls import (
    ResolutionShellControls,
)


class ResolutionEditors:
    """Own writable response and destination editor behavior."""

    def __init__(
        self,
        controller: ResolutionSessionController,
        controls: ResolutionShellControls,
        *,
        draft_loader: Callable[[str], tuple[str | None, str]] | None,
        draft_saver: Callable[[str, str | None, str], None] | None,
        response_validator: Callable[[str], None] | None,
        split_viewer_items: bool,
        destination: ResolutionDestination | None,
        destination_available: bool,
    ) -> None:
        self.controller = controller
        self.controls = controls
        self.draft_loader = draft_loader
        self.draft_saver = draft_saver
        self.response_validator = response_validator
        self.split_viewer_items = split_viewer_items
        self.destination = destination
        self.destination_available = destination_available

    def load_draft(self) -> None:
        item = self.controller.navigation.current_item(self.controller.current_view())
        if item is None:
            self.controller.navigation.selected_option_uid = None
            self.controls.input_area.text = ""
            return
        if self.draft_loader is None:
            draft = _item_draft(item, self.controller.local_drafts)
            selected_option_uid, comment = draft.selected_choice_uid, draft.text
        else:
            selected_option_uid, comment = self.draft_loader(item.uid)
            if selected_option_uid is not None:
                item.option(selected_option_uid)
        self.controller.navigation.selected_option_uid = selected_option_uid
        if selected_option_uid is not None:
            # Reopening a durable draft must align the cursor with the visible
            # checkmark so Enter never toggles a different choice.
            self.controller.navigation.option_cursor_uid = selected_option_uid
        self.controls.input_area.text = comment
        self.controls.input_area.buffer.cursor_position = len(comment)
        target = self.controller.current_response_target()
        if target is not None:
            self.controller.response_state.sync(
                target,
                ResponseDraft(selected_option_uid, comment),
            )

    def save_draft(self) -> bool:
        item = self.controller.navigation.current_item(self.controller.current_view())
        if item is None:
            return True
        if self.response_validator is not None:
            try:
                self.response_validator(self.controls.input_area.text)
            except (TypeError, ValueError) as error:
                self.controller.set_status(str(error))
                return False
        draft = ResponseDraft(
            self.controller.navigation.selected_option_uid,
            self.controls.input_area.text,
        )
        self.controller.local_drafts[item.uid] = draft
        target = self.controller.current_response_target()
        if target is not None and target.item_uid == item.uid:
            self.controller.response_state.sync(target, draft)
        if self.draft_saver is not None:
            self.draft_saver(item.uid, draft.selected_choice_uid, draft.text)
        return True

    def open_item_input(self, *, title: str, clear: bool = False) -> None:
        self.controller.destination_editing["value"] = False
        self.controller.global_comment["value"] = False
        self.controller.response_state.editing = True
        self.controller.response_state.focus_response()
        self.controls.composer.frame.title = title
        self.controller.input_heading["value"] = title
        if clear:
            self.controls.input_area.text = ""
        self.controller.session_navigation.focus("composer")
        get_app().layout.focus(self.controls.input_area)

    def open_global_input(self, *, clear: bool = False) -> None:
        self.controller.destination_editing["value"] = False
        self.controller.global_comment["value"] = True
        self.controller.response_state.editing = True
        self.controller.response_state.focus_response()
        self.controller.other_direction_editor["open"] = False
        self.controls.composer.frame.title = "WHOLE-SET COMMENT"
        self.controller.input_heading["value"] = "WHOLE-SET GUIDANCE"
        if clear:
            self.controller.global_response_draft["value"] = ResponseDraft()
        self.controls.input_area.text = self.controller.global_response_draft[
            "value"
        ].text
        self.controls.input_area.buffer.cursor_position = len(
            self.controls.input_area.text
        )
        self.controller.sync_response_state()
        self.controller.session_navigation.focus("composer")
        get_app().layout.focus(self.controls.input_area)

    def open_destination_input(self) -> None:
        if self.destination is None or not self.destination_available:
            self.controller.set_status("Save-location editing is unavailable here.")
            return
        self.controller.destination_editing["value"] = True
        self.controller.destination_editor_state["value"] = (
            SaveLocationEditorState.create(self.destination)
        )
        self.controller.global_comment["value"] = False
        self.controller.other_direction_editor["open"] = False
        self.controller.response_state.editing = False
        self.controls.destination_frame.title = safe_terminal_text(
            f"{self.destination.label} · CHOOSE PARENT OR EDIT DIRECTLY"
        )
        self.controls.destination_name_field.set_text(self.destination.value)
        self.controller.session_navigation.focus("save_location")
        get_app().layout.focus(self.controls.destination_input)
        self.controller.set_status("")

    def use_destination_parent(self) -> None:
        state = self.controller.destination_editor_state["value"]
        if state is None:
            self.controller.set_status("No parent Context catalog is available here.")
            return
        try:
            candidate = state.choose_cursor_as_parent(
                self.controls.destination_input.text
            )
        except (TypeError, ValueError) as error:
            self.controller.set_status(str(error))
            return
        self.controls.destination_name_field.set_text(candidate)
        get_app().layout.focus(self.controls.destination_input)
        self.controller.set_status(
            f"Parent selected · {state.selected_parent} · edit the exact name or Enter."
        )

    def current_response_heading(self) -> str:
        item = self.controller.navigation.current_item(self.controller.current_view())
        if item is not None and item.issue_presentation is not None:
            return "RESPONSE"
        return "COMMENT ON SELECTED ITEM"
