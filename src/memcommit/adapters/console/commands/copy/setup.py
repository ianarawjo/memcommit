"""Interactive local Context setup for the Copy command."""

from __future__ import annotations

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.adapters.console.commands.copy.workbench import (
    run_copy_and_move_workbench,
)
from memcommit.adapters.console.coordination.copy_and_move.model import (
    CopyAndMoveTuiSetup,
)
from memcommit.adapters.console.terminal.components.context_picker import (
    context_memory_rows,
)
from memcommit.application.operations.copy.application import prepare_copy
from memcommit.application.operations.copy.contracts import (
    CopyMemoriesRequest,
    FrozenCopyMemoriesPlan,
)
from memcommit.application.operations.copy.runtime.store_port import MemoryStoreCopyPort
from memcommit.application.operations.move.contracts import MoveMemoriesRequest


def build_copy_tui_setup(port: MemoryStoreCopyPort) -> CopyAndMoveTuiSetup:
    local_names = port.local_context_names
    if not local_names:
        raise ValueError("Interactive Copy requires a local Context.")
    return CopyAndMoveTuiSetup(
        source_names=local_names,
        local_source_names=local_names,
        into_names=local_names,
        current_context=port.current_context_name,
    )


def choose_copy_setup(
    port: MemoryStoreCopyPort,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> FrozenCopyMemoriesPlan | None:
    """Review and freeze Copy without letting the workbench publish it."""

    setup = build_copy_tui_setup(port)

    def freeze_plan(
        request: CopyMemoriesRequest | MoveMemoriesRequest,
    ) -> FrozenCopyMemoriesPlan:
        if not isinstance(request, CopyMemoriesRequest):
            raise TypeError("Copy workbench supplied the wrong request type.")
        return prepare_copy(request, port=port)

    result = run_copy_and_move_workbench(
        setup,
        kind="COPY",
        inspect_into_context=port.inspect_local_context,
        memory_loader=lambda name: context_memory_rows(
            port.inspect_local_context(name)
        ),
        freeze_plan=freeze_plan,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if result is not None and not isinstance(result, FrozenCopyMemoriesPlan):
        raise TypeError("Copy workbench returned a Move plan.")
    return result


__all__ = ["build_copy_tui_setup", "choose_copy_setup"]
