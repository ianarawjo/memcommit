"""Grant-aware interactive setup for the Copy command."""

from __future__ import annotations

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.adapters.console.coordination.copy_and_move.model import (
    CopyAndMoveTuiSetup,
)
from memcommit.adapters.console.commands.copy_and_move.workbench import (
    run_copy_and_move_workbench,
)
from memcommit.application.context_access.access import (
    ContextAccess,
    GrantedReadStore,
    resolve_context_access,
)
from memcommit.application.capabilities.memory_transfer.application import (
    FrozenCopyMemoriesPlan,
)
from memcommit.application.operations.copy.application import prepare_copy
from memcommit.application.operations.copy.runtime import MemoryStoreCopyPort
from memcommit.application.operations.profile.model import ProfileError
from memcommit.core.context import Context
from memcommit.application.context_access.granted_context_navigation import (
    freeze_granted_context_navigation,
)
from memcommit.adapters.console.terminal.components.context_picker import context_memory_rows
from memcommit.source_projection.presentation import (
    SourceDisplayToken,
    SourceDisplayValue,
    SourceTokenRole,
    combine_source_display_tokens,
)


_RETAINED_COPY_PERMISSIONS = frozenset({"READ"})


def _copy_granted_sources(
    port: MemoryStoreCopyPort,
) -> tuple[
    tuple[str, ...],
    dict[str, ContextAccess],
    tuple[tuple[str, SourceDisplayValue], ...],
]:
    """Freeze explicit public Sources that can authorize retained Copy."""

    if not port.allows_granted_sources:
        return (), {}, ()
    navigation = freeze_granted_context_navigation(port.store)
    accesses: dict[str, ContextAccess] = {}
    annotations: list[tuple[str, SourceDisplayValue]] = []
    for name in navigation.names:
        try:
            access = resolve_context_access(
                port.store,
                name,
                current_name=port.current_context_name,
                required_permission="READ",
            )
        except (FileNotFoundError, ProfileError, RuntimeError, ValueError):
            continue
        if not access.is_granted or access.view is None:
            continue
        if not _RETAINED_COPY_PERMISSIONS <= set(access.view.grant.permissions):
            continue
        accesses[name] = access
        annotations.append(
            (
                name,
                combine_source_display_tokens(
                    navigation.annotations[name],
                    SourceDisplayToken(
                        "COPY + RETAIN",
                        SourceTokenRole.CAPABILITY,
                    ),
                ),
            )
        )
    return tuple(sorted(accesses)), accesses, tuple(annotations)


def _copy_setup_and_granted_sources(
    port: MemoryStoreCopyPort,
) -> tuple[CopyAndMoveTuiSetup, dict[str, ContextAccess]]:
    local_names = port.local_context_names
    if not local_names:
        raise ValueError("Interactive Copy/Move requires a local Context.")
    granted_names, granted_accesses, annotations = _copy_granted_sources(port)
    source_names = tuple(sorted({*local_names, *granted_names}, key=str.casefold))
    return (
        CopyAndMoveTuiSetup(
            source_names=source_names,
            local_source_names=local_names,
            into_names=local_names,
            current_context=(
                port.current_context_name
                if port.current_context_name in local_names
                else None
            ),
            source_annotations=annotations,
        ),
        granted_accesses,
    )


def build_copy_tui_setup(
    port: MemoryStoreCopyPort,
) -> CopyAndMoveTuiSetup:
    """Freeze Copy's local and retained-Grant role catalogs."""

    setup, _accesses = _copy_setup_and_granted_sources(port)
    return setup


def choose_copy_setup(
    port: MemoryStoreCopyPort,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> FrozenCopyMemoriesPlan | None:
    """Review and freeze Copy without letting the workbench publish it."""

    setup, granted_accesses = _copy_setup_and_granted_sources(port)

    def inspect_source(name: str) -> Context:
        access = granted_accesses.get(name)
        if access is None:
            return port.inspect_local_context(name)
        return GrantedReadStore(access).load_direct(name)

    result = run_copy_and_move_workbench(
        setup,
        kind="COPY",
        inspect_source_context=inspect_source,
        inspect_into_context=port.inspect_local_context,
        memory_loader=lambda name: context_memory_rows(inspect_source(name)),
        freeze_copy=lambda request: prepare_copy(request, port=port),
        freeze_move=lambda request: port.freeze_move(request),
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if result is not None and not isinstance(result, FrozenCopyMemoriesPlan):
        raise TypeError("Copy workbench returned a Move plan.")
    return result


__all__ = ["build_copy_tui_setup", "choose_copy_setup"]
