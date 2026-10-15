"""Compose model and effort choices while retaining compatible explicit settings."""

from __future__ import annotations

from memcommit.adapters.console.terminal.components.selection.model import (
    SelectionOption,
)
from memcommit.adapters.console.terminal.components.selection.state import (
    FlatSelectionState,
)
from memcommit.application.initial_setup.configuration import (
    SetupModelSelection,
    select_setup_model,
)
from memcommit.providers.clients.codex_model_catalog import CodexModelOption


class SetupModelSelectionState:
    def __init__(
        self,
        catalog: tuple[CodexModelOption, ...],
        *,
        initial_model: str | None = None,
        initial_reasoning_effort: str | None = None,
    ):
        self.catalog = catalog
        available_model = (
            initial_model
            if any(option.model == initial_model for option in catalog)
            else None
        )
        selected = select_setup_model(catalog, available_model)
        self.models = FlatSelectionState(
            tuple(
                SelectionOption(
                    option.model,
                    option.display_name
                    + (" · RECOMMENDED" if option.is_default else ""),
                )
                for option in catalog
            ),
            cursor_uid=selected.model,
            selected_uid=selected.model,
            allow_empty=False,
        )
        self.reasoning_was_chosen = (
            available_model is not None
            and initial_reasoning_effort is not None
            and initial_reasoning_effort in self.supported_efforts
        )
        self.reasoning_notice = ""
        self._set_reasoning_selection(
            initial_reasoning_effort
            if self.reasoning_was_chosen
            else self.selected_model.default_reasoning_effort
        )

    @property
    def selected_model(self) -> CodexModelOption:
        return next(
            option
            for option in self.catalog
            if option.model == self.models.selected_uid
        )

    @property
    def supported_efforts(self) -> tuple[str, ...]:
        return tuple(
            option.effort for option in self.selected_model.supported_reasoning_efforts
        )

    @property
    def selection(self) -> SetupModelSelection:
        return SetupModelSelection(
            self.selected_model.model,
            self.reasoning.selected_uid if self.reasoning else None,
        )

    def _set_reasoning_selection(self, effort: str | None) -> None:
        options = tuple(
            SelectionOption(option.effort, option.effort, option.description)
            for option in self.selected_model.supported_reasoning_efforts
        )
        self.reasoning = (
            FlatSelectionState(
                options, cursor_uid=effort, selected_uid=effort, allow_empty=False
            )
            if options
            else None
        )

    def move_model(self, delta: int) -> bool:
        previous_effort = self.selection.reasoning_effort
        if not self.models.move(delta):
            return False
        self.models.select_cursor(toggle=False)
        self.reasoning_notice = ""
        if self.reasoning_was_chosen and previous_effort in self.supported_efforts:
            effort = previous_effort
        else:
            effort = self.selected_model.default_reasoning_effort
            if self.reasoning_was_chosen:
                self.reasoning_notice = (
                    "Previous setting is unavailable; using this model's default."
                )
            self.reasoning_was_chosen = False
        self._set_reasoning_selection(effort)
        return True

    def move_reasoning(self, delta: int) -> bool:
        if self.reasoning is None or not self.reasoning.move(delta):
            return False
        self.reasoning.select_cursor(toggle=False)
        self.reasoning_was_chosen = True
        self.reasoning_notice = ""
        return True
