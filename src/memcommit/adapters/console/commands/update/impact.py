"""Update-owned console adapter for directional and saved Impact."""

from __future__ import annotations


import sys

import typer

from memcommit.adapters.console.commands.impact.sessions import (
    update_impact_presentation,
)
from memcommit.adapters.console.commands.update.render import (
    render_plan,
)
from memcommit.adapters.console.commands.update.impact_screen import (
    run_update_impact_screen,
)
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.context_access.access import resolve_context_access
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.adapters.console.commands.impact.update_endpoints import (
    resolve_update_endpoint_accesses,
)
from memcommit.application.operations.update.model import (
    UpdateError,
    plan_update,
    update_inputs_match,
    freeze_update_context_inputs,
)
from memcommit.application.capabilities.context_scope_loading import (
    load_context_and_descendants,
)
from memcommit.core.context_targeting.uid_locator import resolve_exact_or_unique_uid
from memcommit.persistence.store import MemoryStore
from memcommit.providers.errors import QueryProviderError
from memcommit.providers.connection import connect_semantic_provider


def open_saved_update_impact(
    store: MemoryStore,
    *,
    session_uid: str | None,
) -> None:
    from memcommit.persistence.operations.update.receipt_repository import (
        UpdateReceiptRepository,
    )
    from memcommit.adapters.console.commands.impact.sessions import (
        show_process_local_impact,
    )

    receipts = UpdateReceiptRepository(store).list()
    if not receipts:
        raise ValueError("No completed Update receipt exists.")
    receipt = (
        receipts[0]
        if session_uid is None
        else resolve_exact_or_unique_uid(
            receipts, session_uid, uid=lambda item: item.uid, label="Update receipt"
        )
    )
    show_process_local_impact(
        update_impact_presentation(receipt.inputs, receipt.plan, completed=True),
        operation="update",
    )


def run_directional_update_impact(
    *,
    store: MemoryStore,
    current_name: str | None,
    source_name: str | None,
    target_name: str | None,
    source_memory: str | None = None,
    target_memory: str | None = None,
    source_descendants: bool = False,
    target_descendants: bool = False,
) -> None:
    """Preview one explicit or current-filled directional endpoint pair."""

    try:
        endpoints = resolve_update_endpoint_accesses(
            store,
            source_locator=source_name,
            target_locator=target_name,
            current=current_name,
        )
        source_access = endpoints.source.value
        target_access = endpoints.target.value
        source_store = store
        target_store = store
        source_contexts = (
            load_context_and_descendants(source_store, source_access.context_name)
            if source_descendants
            else (source_store.load(source_access.context_name),)
        )
        target_contexts = (
            load_context_and_descendants(target_store, target_access.context_name)
            if target_descendants
            else (target_store.load(target_access.context_name),)
        )
        inputs = freeze_update_context_inputs(
            source_contexts,
            target_contexts,
            source_include_descendants=source_descendants,
            target_include_descendants=target_descendants,
            source_memory_selector=source_memory,
            target_memory_selector=target_memory,
        )
        with CommandProgress(
            "IMPACT UPDATE",
            "connecting provider",
            total=2,
        ) as progress:
            progress.update("planning memory changes", step=2)
            plan = plan_update(
                source_contexts,
                target_contexts,
                connect_semantic_provider,
                source_include_descendants=source_descendants,
                target_include_descendants=target_descendants,
                source_memory_selector=source_memory,
                target_memory_selector=target_memory,
            )

        # Provider latency is not an authorization lease. Re-resolve both
        # endpoints and rebuild both projections before publishing the plan.
        current_source_access = resolve_context_access(
            store,
            endpoints.source.name,
            current_name=current_name,
        )
        current_target_access = resolve_context_access(
            store,
            endpoints.target.name,
            current_name=current_name,
        )
        current_source_store = store
        current_target_store = store
        current_source_contexts = (
            load_context_and_descendants(
                current_source_store, current_source_access.context_name
            )
            if source_descendants
            else (current_source_store.load(current_source_access.context_name),)
        )
        current_target_contexts = (
            load_context_and_descendants(
                current_target_store, current_target_access.context_name
            )
            if target_descendants
            else (current_target_store.load(current_target_access.context_name),)
        )
        if not update_inputs_match(inputs, current_source_contexts, current_target_contexts):
            raise UpdateError(
                "An update endpoint changed while planning; no preview was displayed."
            )
    except (
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        RuntimeError,
        UpdateError,
        ValueError,
    ) as error:
        typer.secho(
            f"Impact error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if sys.stdin.isatty() and sys.stdout.isatty():
        run_update_impact_screen(inputs, plan)
    else:
        render_plan(inputs, plan)


__all__ = ["open_saved_update_impact", "run_directional_update_impact"]
