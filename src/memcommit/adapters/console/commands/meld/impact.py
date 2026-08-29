"""Meld-owned console adapter for saved Impact inspection."""

from __future__ import annotations

import typer

from memcommit.adapters.console.commands.impact.catalog import select_saved_session
from memcommit.adapters.console.commands.impact.sessions import (
    ImpactSessionPresentation,
    meld_impact_presentation,
    run_saved_impact_handoff_loop,
)
from memcommit.adapters.console.commands.meld.sessions import (
    list_meld_session_catalog,
    reload_selected_meld_session,
)
from memcommit.adapters.console.terminal.components.operation_launcher.session import (
    SessionPickerEntry,
)
from memcommit.persistence.store import MemoryStore


def open_saved_meld_impact(
    store: MemoryStore,
    *,
    session_uid: str | None,
) -> None:
    catalog = list_meld_session_catalog(store)
    by_session_uid = {entry.session_uid: entry for entry in catalog}
    entries = tuple(
        SessionPickerEntry(
            kind="meld",
            key=entry.session_uid,
            title=entry.title,
            status=entry.status,
            subtitle=entry.subtitle,
            group=entry.group,
            sort_timestamp=entry.modified_timestamp,
            detail=entry.detail,
            reopen_argv=entry.reopen_argv,
        )
        for entry in catalog
    )
    selected = select_saved_session(
        entries,
        kind="meld",
        title="MEM IMPACT · MELD SESSIONS",
        session_uid=session_uid,
    )
    if selected is None:
        typer.echo("Meld Impact selection cancelled.")
        return
    active_entry = {"value": by_session_uid[selected.key]}

    def load_presentation() -> ImpactSessionPresentation:
        refreshed_catalog = list_meld_session_catalog(store)
        refreshed = next(
            (entry for entry in refreshed_catalog if entry.session_uid == selected.key),
            None,
        )
        if refreshed is None:
            raise ValueError(
                "The saved Meld changed while returning from Apply. Reopen it."
            )
        active_entry["value"] = refreshed
        return meld_impact_presentation(reload_selected_meld_session(store, refreshed))

    def open_owning_workflow() -> None:
        # The owning resume route reloads the catalog identity and enforces its
        # source/target binding checks before presenting the real Apply action.
        from memcommit.adapters.console.commands.meld.command import _resume_picked_meld

        _resume_picked_meld(
            store=store,
            entry=active_entry["value"],
        )

    run_saved_impact_handoff_loop(
        load_presentation=load_presentation,
        open_owning_workflow=open_owning_workflow,
        kind="meld",
    )


__all__ = ["open_saved_meld_impact"]
