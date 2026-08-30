"""Compose Update authority with the shared endpoint-selection interface."""

from __future__ import annotations

from dataclasses import dataclass

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.application.capabilities.authority.context_access import (
    ContextAccess,
    context_access_display_facts,
)
from memcommit.adapters.console.terminal.components.context_picker import context_memory_rows
from memcommit.core.context_targeting.readable_catalog import (
    freeze_profile_readable_context_catalog,
)
from memcommit.adapters.console.terminal.components.endpoint_setup import EndpointSetupMemory
from memcommit.adapters.console.commands.update.workbench import (
    UpdateEndpointSetup,
    choose_update_endpoint_setup,
)
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class UpdateSetupReceipt:
    """Reviewed process-local arguments for one new Update command."""

    source_name: str
    target_name: str
    source_descendants: bool = False
    target_descendants: bool = False
    source_memory_uid: str | None = None
    target_memory_uid: str | None = None


def choose_update_setup(
    store: MemoryStore,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> UpdateSetupReceipt | None:
    """Freeze readable authority, then collect one shared Update setup."""

    local_names = tuple(store.list_context_names())
    if not local_names:
        raise ValueError("Starting Update requires an ordinary local Context.")
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
        raise ValueError("Starting Update requires two readable Contexts.")
    source_name = current_name if current_name in names else names[0]
    target_name = next(name for name in names if name != source_name)
    annotations = tuple(
        (name, context_access_display_facts(catalog.access_for(name)))
        for name in names
        if catalog.access_for(name).is_granted
    )

    def load_memories(role_uid: str, context_name: str):
        if role_uid not in {"A", "B"}:
            raise ValueError("Update Memory projection received an unknown role.")
        return tuple(
            EndpointSetupMemory(context_name, row.selector, row.content)
            for row in context_memory_rows(catalog.load(context_name))
            if row.selector is not None
        )

    selected = choose_update_endpoint_setup(
        UpdateEndpointSetup(
            names=names,
            source_name=source_name,
            target_name=target_name,
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
    return UpdateSetupReceipt(
        selected.source_name,
        selected.target_name,
        source_descendants=selected.source_descendants,
        target_descendants=selected.target_descendants,
        source_memory_uid=selected.source_memory_uid,
        target_memory_uid=selected.target_memory_uid,
    )
