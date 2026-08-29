"""Local-owner interactive setup for the Move command."""

from __future__ import annotations

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.adapters.console.coordination.memory_transfer.model import (
    MemoryTransferTuiSetup,
)
from memcommit.adapters.console.terminal.components.memory_transfer import (
    run_memory_transfer_workbench,
)
from memcommit.application.operations.memory_transfer.application import (
    FrozenMoveMemoriesPlan,
    prepare_move,
)
from memcommit.application.operations.memory_transfer.runtime import (
    MemoryStoreMemoryTransferPort,
)
from memcommit.adapters.console.terminal.components.context_picker import context_memory_rows


def build_move_tui_setup(
    port: MemoryStoreMemoryTransferPort,
) -> MemoryTransferTuiSetup:
    """Freeze Move's ordinary-local Source and Target catalogs."""

    local_names = port.local_context_names
    if not local_names:
        raise ValueError("Interactive Memory transfer requires a local Context.")
    return MemoryTransferTuiSetup(
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
    port: MemoryStoreMemoryTransferPort,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> FrozenMoveMemoriesPlan | None:
    """Review and freeze Move without letting the workbench publish it."""

    setup = build_move_tui_setup(port)
    result = run_memory_transfer_workbench(
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
