"""Process-local navigation and draft state for the common RESPONSES frame."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from memcommit.adapters.console.responses.model import ResponseDraft, ResponseTarget
from memcommit.adapters.console.selection.model import SelectionOption
from memcommit.adapters.console.selection.state import FlatSelectionState


ResponseSection = Literal["DECISION", "RESPONSE"]


@dataclass
class ResponseFrameState:
    """Keep frame interaction stable while operations replace their view.

    Width-dependent wrapping and option hover state remain process-local. The
    selected option and response text cross the adapter boundary only through a
    typed ``ResponseDraft``.
    """

    target_uid: str | None = None
    section: ResponseSection = "RESPONSE"
    # Compatibility name: true now means a choice card owns the flat focus,
    # not that a nested option layer has been opened.
    option_navigation_active: bool = False
    editing: bool = False
    draft: ResponseDraft = field(default_factory=ResponseDraft)
    _choices: FlatSelectionState | None = field(default=None, repr=False)
    _frame_focused: bool = field(default=False, repr=False)

    @property
    def choice_state(self) -> FlatSelectionState | None:
        """Expose the common flat state to the common card renderer."""

        return self._choices

    @property
    def option_cursor_uid(self) -> str | None:
        return None if self._choices is None else self._choices.cursor_uid

    @property
    def other_choice_focused(self) -> bool:
        """Compatibility shim for shells saved before Other became a box."""

        return False

    @other_choice_focused.setter
    def other_choice_focused(self, _focused: bool) -> None:
        # Older frame-boundary code clears this flag while switching panes.
        # There is no synthetic Other row to mutate now.
        return

    @staticmethod
    def _selection_options(target: ResponseTarget) -> tuple[SelectionOption, ...]:
        return tuple(
            SelectionOption(choice.uid, choice.label, choice.text)
            for choice in target.choices
        )

    def sync(
        self,
        target: ResponseTarget,
        draft: ResponseDraft,
        *,
        frame_focused: bool | None = None,
    ) -> None:
        changed = self.target_uid != target.item_uid
        self.target_uid = target.item_uid
        self.draft = draft
        if frame_focused is not None:
            if not isinstance(frame_focused, bool):
                raise ValueError("Response frame focus state must be boolean.")
            if frame_focused != self._frame_focused:
                # Hover is process-local exploration. Crossing the frame
                # boundary restores the checked value without changing it.
                self.restore_choice_cursor()
                if frame_focused:
                    self.section = "DECISION" if target.choices else "RESPONSE"
                    self.option_navigation_active = bool(target.choices)
                self._frame_focused = frame_focused
        if changed:
            # The question is explanatory rather than an independent action.
            # Entering Responses therefore lands on the first visible choice;
            # a prompt without choices lands directly on Response.
            self.section = "DECISION" if target.choices else "RESPONSE"
            self.option_navigation_active = bool(target.choices)
            self.editing = False
        choice_uids = tuple(choice.uid for choice in target.choices)
        if not choice_uids:
            self._choices = None
            self.section = "RESPONSE"
            self.option_navigation_active = False
            return
        options = self._selection_options(target)
        if changed or self._choices is None or self._choices.options != options:
            cursor_uid = (
                draft.selected_choice_uid
                if draft.selected_choice_uid in choice_uids
                else choice_uids[0]
            )
            self._choices = FlatSelectionState(
                options,
                cursor_uid=cursor_uid,
                selected_uid=draft.selected_choice_uid,
            )
        else:
            self._choices.set_selected(draft.selected_choice_uid)

    def sections(self, target: ResponseTarget) -> tuple[ResponseSection, ...]:
        return ("DECISION", "RESPONSE") if target.choices else ("RESPONSE",)

    def move_section(self, target: ResponseTarget, delta: int) -> ResponseSection:
        """Compatibility movement for targets without selectable choices."""

        sections = self.sections(target)
        index = sections.index(self.section) if self.section in sections else 0
        index = max(0, min(index + delta, len(sections) - 1))
        self.section = sections[index]
        self.option_navigation_active = self.section == "DECISION" and bool(
            target.choices
        )
        return self.section

    def open_options(self, target: ResponseTarget) -> bool:
        if not target.choices:
            return False
        self.section = "DECISION"
        self.option_navigation_active = True
        if self._choices is None:
            self.sync(target, self.draft)
        assert self._choices is not None
        if self.draft.selected_choice_uid is not None:
            self._choices.cursor_uid = self.draft.selected_choice_uid
        return True

    def focus_response(self) -> None:
        """Move to the free-form Response stop without changing its draft."""

        self.restore_choice_cursor()
        self.section = "RESPONSE"
        self.option_navigation_active = False

    def restore_choice_cursor(self) -> None:
        """Discard transient hover in favor of the durable checked choice."""

        if self._choices is not None:
            self._choices.reset_cursor_to_selection()

    def move_focus(self, target: ResponseTarget, delta: int) -> ResponseSection:
        """Move through visible choices and then Response as one flat sequence."""

        if isinstance(delta, bool) or not isinstance(delta, int):
            raise ValueError("Response focus movement must be an integer.")
        if not target.choices:
            self.focus_response()
            return self.section
        if self._choices is None:
            self.sync(target, self.draft)
        assert self._choices is not None

        if self.section == "RESPONSE":
            if delta < 0:
                self.section = "DECISION"
                self.option_navigation_active = True
                self.restore_choice_cursor()
            return self.section

        self.section = "DECISION"
        self.option_navigation_active = True
        moved = self._choices.move(delta)
        if delta > 0 and not moved:
            self.focus_response()
        return self.section

    def move_option(self, target: ResponseTarget, delta: int) -> None:
        if not target.choices:
            return
        if self._choices is None:
            self.sync(target, self.draft)
        assert self._choices is not None
        self._choices.move(delta)

    def toggle_current_choice(self, target: ResponseTarget) -> ResponseDraft:
        if self._choices is None or self.option_cursor_uid is None:
            return self.draft
        target.choice(self.option_cursor_uid)
        selected = self._choices.select_cursor(toggle=True)
        self.draft = ResponseDraft(selected, self.draft.text)
        return self.draft

    def close_nested(self) -> bool:
        if self.editing:
            self.editing = False
            return True
        return False
