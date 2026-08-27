"""Compose Reference's terminal setup with its Store port."""

from __future__ import annotations

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.context_targeting.catalog import freeze_granted_context_navigation
from memcommit.context_targeting.tui.picker import context_memory_rows
from memcommit.application.operations.reference.application import (
    FrozenContextReferencePlan,
    FrozenReferencePlan,
    prepare_context_reference,
    prepare_reference,
)
from memcommit.application.operations.reference.runtime import MemoryStoreReferencePort
from memcommit.adapters.interfaces.tui.operations.reference.model import ReferenceTuiSetup
from memcommit.adapters.interfaces.tui.operations.reference.screen import run_reference_tui
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
        port.current_context_name
        if port.current_context_name in local_names
        else None
    )
    target = current or local_names[0]
    source = next((name for name in local_names if name != target), target)

    # Grant navigation supplies explicit public locators only.  Eligibility is
    # narrower than READ visibility because a retained Reference also exports,
    # derives, and saves analysis bytes.  Filtering here prevents a bare Memory
    # UID from ever becoming an implicit scan across authority Contexts.
    navigation = (
        freeze_granted_context_navigation(port.store)
        if port.allows_granted_sources
        else None
    )
    navigation_names = navigation.names if navigation is not None else ()
    navigation_annotations = (
        navigation.annotations if navigation is not None else {}
    )
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
        selected_source=source,
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
) -> FrozenReferencePlan | FrozenContextReferencePlan | None:
    return run_reference_tui(
        build_reference_tui_setup(port),
        memory_loader=lambda name: context_memory_rows(
            port.inspect_memory_source(name)
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
