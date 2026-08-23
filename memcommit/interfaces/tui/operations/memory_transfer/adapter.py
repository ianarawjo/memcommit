"""Compose the Memory-transfer TUI with one Store-backed application port."""

from __future__ import annotations

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.context_targeting.tui.picker import context_memory_rows
from memcommit.memory_transfer_application import (
    FrozenCopyMemoriesPlan,
    FrozenMoveMemoriesPlan,
    prepare_copy,
    prepare_move,
)
from memcommit.memory_transfer_runtime import MemoryStoreMemoryTransferPort
from memcommit.interfaces.tui.operations.memory_transfer.model import (
    MemoryTransferTuiSetup,
)
from memcommit.interfaces.tui.operations.memory_transfer.screen import (
    run_memory_transfer_tui,
)


def build_memory_transfer_tui_setup(
    port: MemoryStoreMemoryTransferPort,
) -> MemoryTransferTuiSetup:
    """Freeze ordinary-local Context names without opening every record."""

    return MemoryTransferTuiSetup(
        context_names=port.local_context_names,
        current_context=(
            port.current_context_name
            if port.current_context_name in port.local_context_names
            else None
        ),
    )


def choose_memory_transfer_setup(
    port: MemoryStoreMemoryTransferPort,
    *,
    kind: str,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> FrozenCopyMemoriesPlan | FrozenMoveMemoriesPlan | None:
    """Review and freeze Copy or Move without letting the TUI publish it."""

    setup = build_memory_transfer_tui_setup(port)
    return run_memory_transfer_tui(
        setup,
        kind=kind,
        inspect_context=port.inspect_local_context,
        memory_loader=lambda name: context_memory_rows(
            port.inspect_local_context(name)
        ),
        freeze_copy=lambda request: prepare_copy(request, port=port),
        freeze_move=lambda request: prepare_move(request, port=port),
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )


__all__ = ["build_memory_transfer_tui_setup", "choose_memory_transfer_setup"]
