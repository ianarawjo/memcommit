"""Compose Meld authority with the shared endpoint-selection interface."""

from __future__ import annotations

from dataclasses import dataclass

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.authority.access import (
    ContextAccess,
    context_access_display_facts,
)
from memcommit.context_targeting.tui.picker import context_memory_rows
from memcommit.commands.meld.target_picker import eligible_meld_targets
from memcommit.context_targeting.readable_catalog import (
    ReadableContextCatalog,
    freeze_profile_readable_context_catalog,
)
from memcommit.interfaces.tui.components.endpoint_setup import EndpointSetupMemory
from memcommit.interfaces.tui.operations.meld import (
    MeldTuiSetup,
    choose_meld_endpoint_setup,
)
from memcommit.store import MemoryStore


@dataclass(frozen=True)
class MeldSetupReceipt:
    """Reviewed process-local arguments for one new Meld command."""

    mode: str
    left_name: str
    right_name: str
    target_name: str | None = None
    create_target: bool = False
    left_descendants: bool = False
    right_descendants: bool = False
    left_memory_uid: str | None = None
    right_memory_uid: str | None = None


def choose_meld_setup(
    store: MemoryStore,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> MeldSetupReceipt | None:
    """Freeze readable authority, then collect one shared Meld setup."""

    setup, catalog = _freeze_meld_tui_setup(store)

    def load_memories(role_uid: str, context_name: str):
        if role_uid not in {"A", "B"}:
            raise ValueError("Meld Memory projection received an unknown role.")
        return tuple(
            EndpointSetupMemory(context_name, row.selector, row.content)
            for row in context_memory_rows(catalog.load(context_name))
            if row.selector is not None
        )

    selected = choose_meld_endpoint_setup(
        setup,
        memory_loader=load_memories,
        new_name_validator=store.assert_context_creatable,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if selected is None:
        return None
    return MeldSetupReceipt(
        mode=selected.mode,
        left_name=selected.left_name,
        right_name=selected.right_name,
        target_name=selected.target_name,
        create_target=selected.create_target,
        left_descendants=selected.left_descendants,
        right_descendants=selected.right_descendants,
        left_memory_uid=selected.left_memory_uid,
        right_memory_uid=selected.right_memory_uid,
    )


def build_meld_tui_setup(store: MemoryStore) -> MeldTuiSetup:
    """Return Meld's frozen public setup values without opening a terminal."""

    setup, _catalog = _freeze_meld_tui_setup(store)
    return setup


def _freeze_meld_tui_setup(
    store: MemoryStore,
) -> tuple[MeldTuiSetup, ReadableContextCatalog]:
    """Freeze one command-local readable catalog and its typed TUI projection."""

    local_names = tuple(store.list_context_names())
    if not local_names:
        raise ValueError("Starting Meld requires an ordinary local Context.")
    current_name = store.current_context_name()
    root_name = current_name if current_name in local_names else local_names[0]
    catalog = freeze_profile_readable_context_catalog(
        store,
        ContextAccess(
            store=store,
            context_name=root_name,
            display_name=root_name,
            attachment_name=None,
            permission="READ",
        ),
        include_query_routes=False,
    )
    names = tuple(catalog.list_context_names())
    if len(names) < 2:
        raise ValueError("Starting Meld requires two readable Contexts.")
    left_name = current_name if current_name in names else names[0]
    right_name = next(name for name in names if name != left_name)
    annotations = tuple(
        (name, context_access_display_facts(catalog.access_for(name)))
        for name in names
        if catalog.access_for(name).is_granted
    )
    eligible_targets = frozenset(
        eligible_meld_targets(store, source_names=("", ""))
    )

    return (
        MeldTuiSetup(
            names=names,
            left_name=left_name,
            right_name=right_name,
            eligible_target_names=eligible_targets,
            current_context=current_name,
            annotations=annotations,
        ),
        catalog,
    )
