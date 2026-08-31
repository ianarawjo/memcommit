"""Sever-owned console adapter for saved Impact inspection."""

from __future__ import annotations

import typer

from memcommit.adapters.console.commands.operation_lifecycle.impact.catalog import select_saved_session
from memcommit.adapters.console.commands.operation_lifecycle.impact.sessions import (
    ImpactSessionPresentation,
    run_saved_impact_handoff_loop,
    sever_impact_presentation,
)
from memcommit.adapters.console.commands.semantic_updates.curate_integrate.sever.sessions import (
    list_sever_session_catalog,
    reload_selected_sever_session,
)
from memcommit.application.operations.semantic_updates.curate_integrate.sever.session_store import SeverSessionStore
from memcommit.persistence.store import MemoryStore


def open_saved_sever_impact(
    store: MemoryStore,
    *,
    session_uid: str | None,
) -> None:
    sessions = SeverSessionStore(store)
    catalog = list_sever_session_catalog(sessions)
    selected = select_saved_session(
        tuple(entry.picker_entry for entry in catalog),
        kind="sever",
        title="MEM IMPACT · SEVER SESSIONS",
        session_uid=session_uid,
    )
    if selected is None:
        typer.echo("Sever Impact selection cancelled.")
        return
    active_session = {"value": None}
    owning_opened = {"value": False}

    def load_presentation() -> ImpactSessionPresentation:
        refreshed_catalog = list_sever_session_catalog(sessions)
        refreshed = next(
            (
                entry
                for entry in refreshed_catalog
                if entry.picker_entry.key == selected.key
            ),
            None,
        )
        if refreshed is None:
            raise ValueError(
                "The saved Sever changed while returning from Apply. Reopen it."
            )
        current = reload_selected_sever_session(sessions, refreshed)
        active_session["value"] = current
        return sever_impact_presentation(current)

    def open_owning_workflow() -> None:
        # Sever retains its ordinary reviewed materialization path; Impact does
        # not bypass its destination validation, CAS save, or Source boundary.
        from memcommit.adapters.console.commands.semantic_updates.curate_integrate.sever.command import _run_workbench

        session = active_session["value"]
        if session is None:
            raise ValueError("The saved Sever session is unavailable.")
        owning_opened["value"] = True
        active_session["value"] = _run_workbench(store, session)

    run_saved_impact_handoff_loop(
        load_presentation=load_presentation,
        open_owning_workflow=open_owning_workflow,
        kind="sever",
    )

    final_session = active_session["value"]
    if owning_opened["value"] and final_session is not None:
        from memcommit.adapters.console.commands.semantic_updates.curate_integrate.sever.command import render_sever

        typer.echo(render_sever(final_session))
        typer.secho(f"Session · {final_session.uid}", fg=typer.colors.CYAN)


__all__ = ["open_saved_sever_impact"]
