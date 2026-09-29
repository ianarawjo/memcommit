"""Optional inline Intent editor; provider work stays in submitted callbacks."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from time import monotonic

from prompt_toolkit.application.current import get_app
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.layout import Dimension
from prompt_toolkit.widgets import TextArea

from memcommit.application.capabilities.resolution.workbench import ResolutionItem
from .screen_state import DecisionScreenState


class IntentEditor:
    def __init__(
        self,
        state: DecisionScreenState,
        *,
        read_text: Callable[[str], str],
        stage_text: Callable[[str, str], None],
        prepare: Callable[[str, str], Awaitable[None]] | None = None,
        validator: Callable[[str], None] | None = None,
        option_uid: Callable[[str], str | None] | None = None,
        title: str = "DIRECTION OR NOTE · OPTIONAL",
    ) -> None:
        self.state = state
        self.read_text, self.stage_text = read_text, stage_text
        self.prepare, self.validator = prepare, validator
        self.option_uid, self.title = option_uid, title
        self.syncing = False
        self.entry_text = ""
        self.drafts: dict[str, Document] = {}
        self.pending = False
        self.started_at = 0.0
        self.area = TextArea(
            text="",
            multiline=False,
            prompt="› ",
            focusable=True,
            focus_on_click=True,
            wrap_lines=False,
            height=Dimension.exact(1),
            read_only=Condition(lambda: self.pending),
            name="compact-resolution-response",
            # The caret marks editing focus; the card owns the border highlight.
            style="",
        )
        self.area.buffer.on_text_changed += self.remember_response_draft
        self.area.buffer.on_cursor_position_changed += self.remember_response_draft
        if self.option_uid is None:
            self.area.buffer.on_text_changed += (
                lambda _buffer: self.stage_inline_response()
            )
        self.sync_response_field()

    def response_available(self, item: ResolutionItem | None) -> bool:
        return item is not None and item.commentable

    def response_supported(self, item: ResolutionItem | None) -> bool:
        return (
            self.response_available(item)
            and self.option_uid is not None
            and item is not None
            and self.option_uid(item.uid) is not None
        )

    def response_selected(self, item: ResolutionItem | None) -> bool:
        return bool(
            self.response_available(item)
            and (
                self.option_uid is None
                or (
                    self.response_supported(item)
                    and item is not None
                    and self.state.selected_for(item) == self.option_uid(item.uid)
                )
            )
        )

    def response_changed(self, item: ResolutionItem) -> bool:
        draft = self.drafts.get(item.uid)
        return draft is not None and draft.text != self.read_text(item.uid)

    def response_needs_refresh(self, item: ResolutionItem) -> bool:
        return self.response_selected(item) and self.response_changed(item)

    def response_choice_index(self, item: ResolutionItem | None) -> int | None:
        if not self.response_supported(item) or item is None or self.option_uid is None:
            return None
        target_uid = self.option_uid(item.uid)
        return next(
            (
                index
                for index, option in enumerate(item.options)
                if option.uid == target_uid
            ),
            None,
        )

    def sync_response_field(self) -> None:
        item = self.state.current_issue()
        if not self.response_available(item) or item is None:
            return
        current = self.read_text(item.uid).replace("\r", " ").replace("\n", " ")
        self.syncing = True
        try:
            self.area.buffer.document = self.drafts.get(
                item.uid, Document(current, len(current))
            )
            self.entry_text = current
        finally:
            self.syncing = False

    def response_is_valid(self) -> bool:
        if self.validator is None:
            return True
        try:
            self.validator(self.area.text)
        except (TypeError, ValueError) as error:
            self.state.status_message = str(error)
            return False
        return True

    def stage_inline_response(self, *, commit_unchanged: bool = False) -> None:
        item = self.state.current_issue()
        if (
            self.syncing
            or item is None
            or not self.response_available(item)
            or not self.response_is_valid()
        ):
            return
        if (
            self.option_uid is not None
            and not commit_unchanged
            and self.area.text == self.entry_text
        ):
            return
        self.stage_text(item.uid, self.area.text)
        self.entry_text = self.area.text
        self.state.status_message = ""

    def open_response(self) -> None:
        if not self.response_selected(self.state.current_issue()):
            return
        self.sync_response_field()
        self.state.status_message = ""
        get_app().layout.focus(self.area)

    def complete_response(
        self,
        delta: int,
        move_row: Callable[[int], None],
        *,
        commit_unchanged: bool = False,
    ) -> None:
        if not self.response_is_valid():
            return
        self.stage_inline_response(commit_unchanged=commit_unchanged)
        if self.option_uid is not None and delta == 0:
            # Enter refreshes the result but never converts the editor into a
            # read-only card. The next Backspace is ordinary text deletion.
            return
        move_row(delta)

    async def prepare_response_preview(
        self, delta, move_row, *, commit_unchanged=False
    ):
        if not self.response_is_valid():
            return
        item = self.state.current_issue()
        if self.prepare is not None and item is not None:
            current_app = get_app()
            current_app.invalidate()
            try:
                await self.prepare(item.uid, self.area.text)
            except (OSError, RuntimeError, TypeError, ValueError) as error:
                self.state.status_message = "Preview failed · " + str(error)
                return
            finally:
                self.pending = False
                current_app.invalidate()
            if current_app.is_done:
                return
        self.complete_response(delta, move_row, commit_unchanged=commit_unchanged)

    def submit_response(self, delta, move_row, *, commit_unchanged=False):
        item = self.state.current_issue()
        if (
            self.prepare is not None
            and item is not None
            and self.area.text.strip()
            and self.area.text != self.read_text(item.uid)
            and self.response_is_valid()
        ):
            # Freeze input before scheduling so queued edits cannot change the
            # exact instruction whose result is still being prepared.
            self.pending = True
            self.started_at = monotonic()
            self.state.status_message = ""
            get_app().create_background_task(
                self.prepare_response_preview(
                    delta,
                    move_row,
                    commit_unchanged=commit_unchanged,
                )
            )
        else:
            self.complete_response(delta, move_row, commit_unchanged=commit_unchanged)

    def remember_response_draft(self, buffer) -> None:
        item = self.state.current_issue()
        if not self.syncing and item is not None:
            self.drafts[item.uid] = buffer.document
            self.state.status_message = ""
