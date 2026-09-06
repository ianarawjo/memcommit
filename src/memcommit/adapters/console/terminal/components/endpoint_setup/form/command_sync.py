"""Keep endpoint selections and the editable execution command synchronized."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from memcommit.adapters.console.terminal.components.command_editor import (
    CommandDraft,
    CommandEditorControl,
)
from memcommit.adapters.console.terminal.components.endpoint_setup.command_binding import (
    DraftValidator,
    EndpointCommandBinding,
)
from memcommit.adapters.console.terminal.components.endpoint_setup.model import (
    EndpointSetupDraft,
    EndpointSetupSpec,
)
from memcommit.adapters.console.terminal.components.horizontal_choice import (
    HorizontalChoiceState,
)
from .endpoint_editor import EndpointEditor


class EndpointCommandSync:
    """Use the operation's existing codec; commit a decoded draft to its editors."""

    def __init__(
        self,
        spec: EndpointSetupSpec,
        editors: Mapping[str, EndpointEditor],
        mode_state: HorizontalChoiceState,
        *,
        binding: EndpointCommandBinding | None,
        validate_draft: DraftValidator | None,
        on_applied: Callable[[], None],
    ) -> None:
        self.spec = spec
        self.editors = editors
        self.mode_state = mode_state
        self.binding = binding
        self.validate_draft = validate_draft
        self.on_applied = on_applied
        self.control = (
            CommandEditorControl.create(
                CommandDraft(
                    review=lambda: binding.review(self.checked_draft()),
                    apply_argv=self.apply_command_argv,
                    form=binding.form,
                ),
                action_label=f"RUN EXACT {spec.command_verb} COMMAND",
                incomplete_action="FIX THE RED COMMAND BEFORE RUNNING",
                input_name="endpoint-form-proposed-command",
            )
            if binding is not None
            else None
        )

    def make_draft(self) -> EndpointSetupDraft:
        mode_uid = self.mode_state.selected_uid
        return EndpointSetupDraft(
            mode_uid,
            tuple(
                self.editors[uid].collect_value()
                for uid in self.spec.active_role_uids(mode_uid)
            ),
        )

    def checked_draft(self) -> EndpointSetupDraft:
        draft = self.make_draft()
        message = (
            self.validate_draft(draft) if self.validate_draft is not None else None
        )
        if message:
            raise ValueError(message)
        return draft

    def apply_command_draft(self, draft: EndpointSetupDraft) -> None:
        # Resolve every selected Memory before moving any input. A failure in a
        # later endpoint must not partially apply the edited command above it.
        resolved_memory_uids: dict[str, str] = {}
        for value in draft.values:
            if value.memory_uid is not None:
                resolved_memory_uids[value.role_uid] = self.editors[
                    value.role_uid
                ].memory_focus.resolve_selector(value.context_name, value.memory_uid)
        self.mode_state.choose(draft.mode_uid)
        for value in draft.values:
            self.editors[value.role_uid].apply_value(
                value, resolved_memory_uids.get(value.role_uid)
            )
        self.on_applied()

    def apply_command_argv(self, argv: tuple[str, ...]) -> None:
        if self.binding is None:
            raise RuntimeError("This Endpoint Setup has no editable command.")
        self.apply_command_draft(
            self.binding.decode(
                argv,
                spec=self.spec,
                validate_draft=self.validate_draft,
            )
        )
