"""Compose model and effort choices while retaining compatible explicit settings."""

from __future__ import annotations

from memcommit.adapters.console.terminal.components.selection.model import (
    SelectionOption,
)
from memcommit.adapters.console.terminal.components.selection.state import (
    SingleSelectionState,
)
from memcommit.application.initial_setup.configuration import (
    SetupModelSelection,
    select_setup_model,
)
from memcommit.providers.clients.codex_model_catalog import CodexModelOption


class SetupModelAndReasoningSelectionState:
    def __init__(
        self,
        catalog: tuple[CodexModelOption, ...],
        *,
        last_selected_model: str | None = None,
        last_selected_reasoning_effort: str | None = None,
    ):
        self.catalog = catalog
        model_ids = {option.model for option in catalog}

        available_model = last_selected_model
        if last_selected_model not in model_ids:
            available_model = None
        selected = select_setup_model(catalog=catalog, model=available_model)
        self.models = SingleSelectionState(
            options=tuple(
                SelectionOption(
                    value=option.model,
                    label=option.display_name
                    + (" · RECOMMENDED" if option.is_default else ""),
                )
                for option in catalog
            ),
            cursor_value=selected.model,
            selected_value=selected.model,
            allow_empty=False,
        )
        self.reasoning_was_chosen = (
            available_model is not None
            and last_selected_reasoning_effort is not None
            and last_selected_reasoning_effort in self.supported_efforts
        )
        self._set_reasoning_selection(
            last_selected_reasoning_effort
            if self.reasoning_was_chosen
            else self.selected_model.default_reasoning_effort
        )

    @property
    def selected_model(self) -> CodexModelOption:
        return next(
            option
            for option in self.catalog
            if option.model == self.models.selected_value
        )

    @property
    def supported_efforts(self) -> tuple[str, ...]:
        return tuple(
            option.effort for option in self.selected_model.supported_reasoning_efforts
        )

    @property
    def selection(self) -> SetupModelSelection:
        return SetupModelSelection(
            model=self.selected_model.model,
            reasoning_effort=self.reasoning.selected_value if self.reasoning else None,
        )

    def _set_reasoning_selection(self, effort: str | None) -> None:
        options = tuple(
            SelectionOption(
                value=option.effort,
                label=option.effort,
                description=option.description,
            )
            for option in self.selected_model.supported_reasoning_efforts
        )
        self.reasoning = (
            SingleSelectionState(
                options=options, cursor_value=effort, selected_value=effort, allow_empty=False
            )
            if options
            else None
        )

    def move_model(self, delta: int) -> bool:
        previous_effort = self.selection.reasoning_effort
        if not self.models.move(delta):
            return False
        self.models.select_cursor(toggle=False)
        if self.reasoning_was_chosen and previous_effort in self.supported_efforts:
            effort = previous_effort
        else:
            effort = self.selected_model.default_reasoning_effort
            self.reasoning_was_chosen = False
        self._set_reasoning_selection(effort)
        return True

    def move_reasoning(self, delta: int) -> bool:
        if self.reasoning is None or not self.reasoning.move(delta):
            return False
        self.reasoning.select_cursor(toggle=False)
        self.reasoning_was_chosen = True
        return True
