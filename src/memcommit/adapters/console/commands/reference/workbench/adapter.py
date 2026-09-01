"""Compose Reference's terminal workbench with its Store port."""

from __future__ import annotations

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.application.context_access.granted_context_navigation import (
    freeze_granted_context_navigation,
)
from memcommit.adapters.console.terminal.components.context_picker import (
    context_memory_rows,
)
from memcommit.application.operations.reference.application import (
    FrozenReferencePlan,
    prepare_reference,
)
from memcommit.application.operations.reference.runtime import MemoryStoreReferencePort
from memcommit.adapters.console.commands.reference.endpoint_setup import (
    ReferenceTuiSetup,
    run_reference_tui,
)
from memcommit.source_projection.presentation import (
    SourceDisplayToken,
    SourceTokenRole,
    combine_source_display_tokens,
)


def build_reference_tui_setup(port: MemoryStoreReferencePort) -> ReferenceTuiSetup:
    local_names = port.local_context_names
    if not local_names:
        raise ValueError("Interactive Reference requires at least one local Context.")
    current = (
        port.current_context_name if port.current_context_name in local_names else None
    )
    target = current or local_names[0]
    source = next((name for name in local_names if name != target), target)

    # Grant navigation supplies explicit public locators only. READ is the
    # retained-output boundary for an exact Memory snapshot, while a bare
    # Memory UID still never scans authority Contexts implicitly.
    navigation = (
        freeze_granted_context_navigation(port.store)
        if port.allows_granted_sources
        else None
    )
    navigation_names = navigation.names if navigation is not None else ()
    navigation_annotations = navigation.annotations if navigation is not None else {}
    granted_names: list[str] = []
    annotations = []
    for name in navigation_names:
        try:
            access = port.authorize_memory_source(name)
        except (FileNotFoundError, RuntimeError, ValueError):
            continue
        if not access.is_granted:
            continue
        granted_names.append(name)
        annotations.append(
            (
                name,
                combine_source_display_tokens(
                    navigation_annotations[name],
                    SourceDisplayToken(
                        "REFERENCE",
                        SourceTokenRole.CAPABILITY,
                    ),
                ),
            )
        )
    memory_source_names = tuple(sorted(set(local_names) | set(granted_names)))
    selected_memory_source = (
        source
        if source != target
        else next(
            (name for name in memory_source_names if name != target),
            source,
        )
    )
    return ReferenceTuiSetup(
        names=local_names,
        selected_source=selected_memory_source,
        selected_target=target,
        current_context=current,
        memory_source_names=memory_source_names,
        memory_source_selectable_names=frozenset(memory_source_names),
        selected_memory_source=selected_memory_source,
        memory_source_annotations=tuple(annotations),
    )


def choose_reference_setup(
    port: MemoryStoreReferencePort,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> FrozenReferencePlan | None:
    return run_reference_tui(
        build_reference_tui_setup(port),
        memory_loader=lambda name: context_memory_rows(
            port.inspect_memory_source(name)
        ),
        prepare=lambda request: prepare_reference(request, port=port),
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )


__all__ = ["build_reference_tui_setup", "choose_reference_setup"]
