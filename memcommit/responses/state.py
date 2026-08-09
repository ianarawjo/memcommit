"""Process-local navigation and draft state for the common RESPONSES frame."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from memcommit.responses.model import ResponseDraft, ResponseTarget
from memcommit.selection.model import SelectionOption
from memcommit.selection.state import FlatSelectionState


ResponseSection = Literal["DECISION", "RESPONSE"]
_OTHER_CHOICE_UID = "__memcommit_response_other__"


@dataclass
class ResponseFrameState:
    """Keep frame interaction stable while operations replace their view.

    Width-dependent wrapping and option hover state remain process-local. The
    selected option and response text cross the adapter boundary only through a
    typed ``ResponseDraft``.
    """

    target_uid: str | None = None
    section: ResponseSection = "RESPONSE"
    option_navigation_active: bool = False
    editing: bool = False
    draft: ResponseDraft = field(default_factory=ResponseDraft)
    _choices: FlatSelectionState | None = field(default=None, repr=False)

    @property
    def choice_state(self) -> FlatSelectionState | None:
        """Expose the common flat state to the common card renderer."""

        return self._choices

    @property
    def option_cursor_uid(self) -> str | None:
        if self._choices is None or self._choices.cursor_uid == _OTHER_CHOICE_UID:
            return None
        return self._choices.cursor_uid

    @property
    def other_choice_focused(self) -> bool:
        return (
            self._choices is not None and self._choices.cursor_uid == _OTHER_CHOICE_UID
        )

    @other_choice_focused.setter
    def other_choice_focused(self, focused: bool) -> None:
        if self._choices is None:
            return
        if focused:
            self._choices.cursor_uid = _OTHER_CHOICE_UID
            return
        if self._choices.cursor_uid == _OTHER_CHOICE_UID:
            ordinary_uids = tuple(
                option.uid
                for option in self._choices.options
                if option.uid != _OTHER_CHOICE_UID
            )
            if ordinary_uids:
                self._choices.cursor_uid = (
                    self._choices.selected_uid
                    if self._choices.selected_uid in ordinary_uids
                    else ordinary_uids[0]
                )

    @staticmethod
    def _selection_options(target: ResponseTarget) -> tuple[SelectionOption, ...]:
        if any(choice.uid == _OTHER_CHOICE_UID for choice in target.choices):
            raise ValueError("Response choice UID collides with the Other control.")
        return tuple(
            SelectionOption(choice.uid, choice.label, choice.text)
            for choice in target.choices
        ) + (
            SelectionOption(
                _OTHER_CHOICE_UID,
                target.other_choice_label,
                "Write a different answer in Response.",
            ),
        )

    def sync(self, target: ResponseTarget, draft: ResponseDraft) -> None:
        changed = self.target_uid != target.item_uid
        self.target_uid = target.item_uid
        self.draft = draft
        if changed:
            self.section = "DECISION" if target.has_decision else "RESPONSE"
            self.option_navigation_active = False
            self.editing = False
        choice_uids = tuple(choice.uid for choice in target.choices)
        if not choice_uids:
            self._choices = None
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
            if changed:
                self._choices.reset_cursor_to_selection()

    def sections(self, target: ResponseTarget) -> tuple[ResponseSection, ...]:
        return ("DECISION", "RESPONSE") if target.has_decision else ("RESPONSE",)

    def move_section(self, target: ResponseTarget, delta: int) -> ResponseSection:
        sections = self.sections(target)
        index = sections.index(self.section) if self.section in sections else 0
        index = max(0, min(index + delta, len(sections) - 1))
        self.section = sections[index]
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
        elif self._choices.cursor_uid == _OTHER_CHOICE_UID:
            self._choices.cursor_uid = target.choices[0].uid
        return True

    def move_option(self, target: ResponseTarget, delta: int) -> None:
        if not target.choices:
            return
        if self._choices is None:
            self.sync(target, self.draft)
        assert self._choices is not None
        self._choices.move(delta)

    def toggle_current_choice(self, target: ResponseTarget) -> ResponseDraft:
        if self.other_choice_focused:
            assert self._choices is not None
            self._choices.set_selected(None)
            self.draft = ResponseDraft(None, self.draft.text)
            return self.draft
        if self._choices is None or self.option_cursor_uid is None:
            return self.draft
        target.choice(self.option_cursor_uid)
        selected = self._choices.select_cursor(toggle=True)
        self.draft = ResponseDraft(selected, self.draft.text)
        return self.draft

    def close_nested(self) -> bool:
        if self.option_navigation_active:
            self.option_navigation_active = False
            self.other_choice_focused = False
            return True
        if self.editing:
            self.editing = False
            return True
        return False
