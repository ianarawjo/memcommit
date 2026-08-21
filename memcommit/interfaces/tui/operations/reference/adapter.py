"""Compose Reference's terminal setup with its Store port."""

from __future__ import annotations

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.context_targeting.tui.picker import context_memory_rows
from memcommit.reference_application import (
    FrozenContextReferencePlan,
    FrozenReferencePlan,
    prepare_context_reference,
    prepare_reference,
)
from memcommit.reference_runtime import MemoryStoreReferencePort
from memcommit.interfaces.tui.operations.reference.model import ReferenceTuiSetup
from memcommit.interfaces.tui.operations.reference.screen import run_reference_tui


def build_reference_tui_setup(port: MemoryStoreReferencePort) -> ReferenceTuiSetup:
    names = port.local_context_names
    if not names:
        raise ValueError("Interactive Reference requires at least one local Context.")
    current = port.current_context_name if port.current_context_name in names else None
    target = current or names[0]
    source = next((name for name in names if name != target), target)
    return ReferenceTuiSetup(
        names=names,
        selected_source=source,
        selected_target=target,
        current_context=current,
    )


def choose_reference_setup(
    port: MemoryStoreReferencePort,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> FrozenReferencePlan | FrozenContextReferencePlan | None:
    return run_reference_tui(
        build_reference_tui_setup(port),
        memory_loader=lambda name: context_memory_rows(
            port.inspect_local_context(name)
        ),
        prepare=lambda request: prepare_reference(request, port=port),
        prepare_context=lambda request: prepare_context_reference(
            request,
            port=port,
        ),
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )


__all__ = ["build_reference_tui_setup", "choose_reference_setup"]
