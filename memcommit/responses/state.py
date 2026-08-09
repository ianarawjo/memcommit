"""Process-local navigation and draft state for the common RESPONSES frame."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from memcommit.responses.model import ResponseDraft, ResponseTarget


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
    option_navigation_active: bool = False
    option_cursor_uid: str | None = None
    other_choice_focused: bool = False
    editing: bool = False
    draft: ResponseDraft = field(default_factory=ResponseDraft)

    def sync(self, target: ResponseTarget, draft: ResponseDraft) -> None:
        changed = self.target_uid != target.item_uid
        self.target_uid = target.item_uid
        self.draft = draft
        if changed:
            self.section = "DECISION" if target.has_decision else "RESPONSE"
            self.option_navigation_active = False
            self.other_choice_focused = False
            self.editing = False
        choice_uids = tuple(choice.uid for choice in target.choices)
        if draft.selected_choice_uid in choice_uids:
            self.option_cursor_uid = draft.selected_choice_uid
        elif self.option_cursor_uid not in choice_uids:
            self.option_cursor_uid = choice_uids[0] if choice_uids else None

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
        self.other_choice_focused = False
        choice_uids = tuple(choice.uid for choice in target.choices)
        if self.draft.selected_choice_uid in choice_uids:
            self.option_cursor_uid = self.draft.selected_choice_uid
        elif self.option_cursor_uid not in choice_uids:
            self.option_cursor_uid = choice_uids[0]
        return True

    def move_option(self, target: ResponseTarget, delta: int) -> None:
        choice_uids = tuple(choice.uid for choice in target.choices)
        if not choice_uids:
            return
        if self.other_choice_focused:
            index = len(choice_uids)
        elif self.option_cursor_uid in choice_uids:
            index = choice_uids.index(self.option_cursor_uid)
        else:
            index = 0
        next_index = max(0, min(index + delta, len(choice_uids)))
        self.other_choice_focused = next_index == len(choice_uids)
        if not self.other_choice_focused:
            self.option_cursor_uid = choice_uids[next_index]

    def toggle_current_choice(self, target: ResponseTarget) -> ResponseDraft:
        if self.other_choice_focused:
            self.draft = ResponseDraft(None, self.draft.text)
            return self.draft
        if self.option_cursor_uid is None:
            return self.draft
        target.choice(self.option_cursor_uid)
        selected = (
            None
            if self.draft.selected_choice_uid == self.option_cursor_uid
            else self.option_cursor_uid
        )
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
