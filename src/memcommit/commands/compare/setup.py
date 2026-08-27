"""Compose Compare authority with the shared endpoint-selection interface."""

from __future__ import annotations

from dataclasses import dataclass

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.application.authority.access import (
    ContextAccess,
    context_access_display_facts,
)
from memcommit.core.context_targeting.tui.picker import context_memory_rows
from memcommit.commands.shared.readable_context_catalog import (
    freeze_profile_readable_context_catalog,
)
from memcommit.adapters.interfaces.tui.components.endpoint_setup import EndpointSetupMemory
from memcommit.adapters.interfaces.tui.operations.compare import (
    CompareTuiSetup,
    choose_compare_endpoint_setup,
)
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class CompareSetupReceipt:
    """Reviewed process-local arguments for one new Compare command."""

    reference_name: str
    compared_name: str
    reference_descendants: bool = False
    compared_descendants: bool = False
    reference_memory_uid: str | None = None
    compared_memory_uid: str | None = None


def choose_compare_setup(
    store: MemoryStore,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> CompareSetupReceipt | None:
    """Freeze readable authority, then collect one shared Compare setup."""

    local_names = tuple(store.list_context_names())
    if not local_names:
        raise ValueError("Starting Compare requires an ordinary local Context.")
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
        raise ValueError("Starting Compare requires two readable Contexts.")
    reference_name = current_name if current_name in names else names[0]
    peer_name = next(name for name in names if name != reference_name)
    annotations = tuple(
        (name, context_access_display_facts(catalog.access_for(name)))
        for name in names
        if catalog.access_for(name).is_granted
    )

    def load_memories(role_uid: str, context_name: str):
        if role_uid not in {"A", "B"}:
            raise ValueError("Compare Memory projection received an unknown role.")
        return tuple(
            EndpointSetupMemory(context_name, row.selector, row.content)
            for row in context_memory_rows(catalog.load(context_name))
            if row.selector is not None
        )

    selected = choose_compare_endpoint_setup(
        CompareTuiSetup(
            names=names,
            reference_name=reference_name,
            peer_name=peer_name,
            current_context=current_name,
            annotations=annotations,
        ),
        memory_loader=load_memories,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if selected is None:
        return None
    return CompareSetupReceipt(
        selected.reference_name,
        selected.peer_name,
        reference_descendants=selected.reference_descendants,
        compared_descendants=selected.peer_descendants,
        reference_memory_uid=selected.reference_memory_uid,
        compared_memory_uid=selected.peer_memory_uid,
    )
