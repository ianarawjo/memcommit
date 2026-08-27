"""Compose the Memory-transfer TUI with one Store-backed application port."""

from __future__ import annotations

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.application.authority.access import (
    ContextAccess,
    GrantedReadStore,
    resolve_context_access,
)
from memcommit.context import Context
from memcommit.core.context_targeting.catalog import freeze_granted_context_navigation
from memcommit.core.context_targeting.tui.picker import context_memory_rows
from memcommit.application.operations.memory_transfer.application import (
    FrozenCopyMemoriesPlan,
    FrozenMoveMemoriesPlan,
    prepare_copy,
    prepare_move,
)
from memcommit.application.operations.memory_transfer.runtime import MemoryStoreMemoryTransferPort
from memcommit.adapters.interfaces.tui.operations.memory_transfer.model import (
    MemoryTransferTuiSetup,
)
from memcommit.adapters.interfaces.tui.operations.memory_transfer.screen import (
    run_memory_transfer_tui,
)
from memcommit.application.operations.profile.model import ProfileError
from memcommit.source_projection.presentation import (
    SourceDisplayToken,
    SourceDisplayValue,
    SourceTokenRole,
    combine_source_display_tokens,
)


_RETAINED_COPY_PERMISSIONS = frozenset(
    {"READ", "DERIVE", "EXPORT", "SAVE_ANALYSIS"}
)


def _copy_granted_sources(
    port: MemoryStoreMemoryTransferPort,
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


def _setup_and_granted_sources(
    port: MemoryStoreMemoryTransferPort,
    *,
    kind: str,
) -> tuple[MemoryTransferTuiSetup, dict[str, ContextAccess]]:
    operation = kind.upper()
    if operation not in {"COPY", "MOVE"}:
        raise ValueError("Memory transfer kind must be COPY or MOVE.")
    local_names = port.local_context_names
    if not local_names:
        raise ValueError("Interactive Memory transfer requires a local Context.")
    granted_names: tuple[str, ...] = ()
    granted_accesses: dict[str, ContextAccess] = {}
    annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()
    if operation == "COPY":
        granted_names, granted_accesses, annotations = _copy_granted_sources(port)
    source_names = tuple(sorted({*local_names, *granted_names}, key=str.casefold))
    setup = MemoryTransferTuiSetup(
        source_names=source_names,
        local_source_names=local_names,
        into_names=local_names,
        current_context=(
            port.current_context_name
            if port.current_context_name in local_names
            else None
        ),
        source_annotations=annotations,
    )
    return setup, granted_accesses


def build_memory_transfer_tui_setup(
    port: MemoryStoreMemoryTransferPort,
    *,
    kind: str,
) -> MemoryTransferTuiSetup:
    """Freeze role-specific Copy or Move Context catalogs."""

    setup, _accesses = _setup_and_granted_sources(port, kind=kind)
    return setup


def choose_memory_transfer_setup(
    port: MemoryStoreMemoryTransferPort,
    *,
    kind: str,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> FrozenCopyMemoriesPlan | FrozenMoveMemoriesPlan | None:
    """Review and freeze Copy or Move without letting the TUI publish it."""

    setup, granted_accesses = _setup_and_granted_sources(port, kind=kind)

    def inspect_source(name: str) -> Context:
        access = granted_accesses.get(name)
        if access is None:
            return port.inspect_local_context(name)
        return GrantedReadStore(access).load_direct(name)

    return run_memory_transfer_tui(
        setup,
        kind=kind,
        inspect_source_context=inspect_source,
        inspect_into_context=port.inspect_local_context,
        memory_loader=lambda name: context_memory_rows(
            inspect_source(name)
        ),
        freeze_copy=lambda request: prepare_copy(request, port=port),
        freeze_move=lambda request: prepare_move(request, port=port),
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )


__all__ = ["build_memory_transfer_tui_setup", "choose_memory_transfer_setup"]
