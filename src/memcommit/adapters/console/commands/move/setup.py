"""Local-owner interactive setup for the Move command."""

from __future__ import annotations

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.adapters.console.coordination.copy_and_move.model import (
    CopyAndMoveTuiSetup,
)
from memcommit.adapters.console.terminal.components.copy_and_move import (
    run_copy_and_move_workbench,
)
from memcommit.application.capabilities.memory_transfer.application import (
    FrozenMoveMemoriesPlan,
)
from memcommit.application.operations.move.application import prepare_move
from memcommit.application.operations.move.runtime import MemoryStoreMovePort
from memcommit.adapters.console.terminal.components.context_picker import context_memory_rows


def build_move_tui_setup(
    port: MemoryStoreMovePort,
) -> CopyAndMoveTuiSetup:
    """Freeze Move's ordinary-local Source and Target catalogs."""

    local_names = port.local_context_names
    if not local_names:
        raise ValueError("Interactive Copy/Move requires a local Context.")
    return CopyAndMoveTuiSetup(
        source_names=local_names,
        local_source_names=local_names,
        into_names=local_names,
        current_context=(
            port.current_context_name
            if port.current_context_name in local_names
            else None
        ),
    )


def choose_move_setup(
    port: MemoryStoreMovePort,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> FrozenMoveMemoriesPlan | None:
    """Review and freeze Move without letting the workbench publish it."""

    setup = build_move_tui_setup(port)
    result = run_copy_and_move_workbench(
        setup,
        kind="MOVE",
        inspect_source_context=port.inspect_local_context,
        inspect_into_context=port.inspect_local_context,
        memory_loader=lambda name: context_memory_rows(
            port.inspect_local_context(name)
        ),
        freeze_copy=lambda request: port.freeze_copy(request),
        freeze_move=lambda request: prepare_move(request, port=port),
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if result is not None and not isinstance(result, FrozenMoveMemoriesPlan):
        raise TypeError("Move workbench returned a Copy plan.")
    return result


__all__ = ["build_move_tui_setup", "choose_move_setup"]
