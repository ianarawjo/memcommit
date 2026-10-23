"""Compose Edit's console workbench with EDIT-aware Context access."""

from __future__ import annotations

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output


from memcommit.adapters.console.terminal.components.context_picker import (
    context_memory_rows,
)
from memcommit.application.operations.edit.application import (
    FrozenEditPlan,
    prepare_edit,
)
from memcommit.application.operations.edit.runtime import MemoryStoreEditPort
from memcommit.adapters.console.commands.edit.workbench.model import EditTuiSetup
from memcommit.adapters.console.commands.edit.workbench.screen import run_edit_tui


def build_edit_tui_setup(
    port: MemoryStoreEditPort,
    *,
    requested_context: str | None = None,
) -> EditTuiSetup:
    access = port.access(requested_context)
    selected = access.access_name
    return EditTuiSetup(
        names=(selected,),
        selectable_names=frozenset({selected}),
        selected_context=selected,
        current_context=port.current_context_name,
    )


def choose_edit_setup(
    port: MemoryStoreEditPort,
    *,
    requested_context: str | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> FrozenEditPlan | None:
    return run_edit_tui(
        build_edit_tui_setup(port, requested_context=requested_context),
        memory_loader=lambda name: context_memory_rows(port.inspect_context(name)),
        prepare=lambda request: prepare_edit(request, port=port),
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )


__all__ = ["build_edit_tui_setup", "choose_edit_setup"]
