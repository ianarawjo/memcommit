"""One typed Sync operation; console adapters render only committed results."""

from uuid import uuid4
from dataclasses import replace
from .model import SyncPort, SyncRequest, SyncResult
from .automatic.settings import toggle_automatic_selection
from memcommit.application.capabilities.import_export.export_documents import (
    publish_export_documents,
)


def run_sync(request: SyncRequest, port: SyncPort) -> SyncResult:
    if not isinstance(request, SyncRequest):
        raise TypeError("Expected SyncRequest.")
    if any(
        not isinstance(value, bool)
        for value in (
            request.recursive,
            request.all_contexts,
            request.toggle_always,
            request.automatic,
        )
    ):
        raise TypeError("Sync flags must be boolean.")
    if request.automatic and request.toggle_always:
        raise ValueError("Automatic execution cannot toggle its own settings.")
    with port.execution_boundary():
        return _run_sync_locked(request, port)


def _run_sync_locked(request, port):
    selection = port.freeze_selection(request)
    settings = port.settings.load()
    updated_policies, automatic_change = settings["policies"], None
    if request.toggle_always:
        updated_policies, automatic_change = toggle_automatic_selection(
            selection, settings["policies"]
        )
        if not automatic_change.enabled:
            port.settings.save(
                {**settings, "policies": updated_policies},
                expected_revision=settings["revision"],
            )
            return SyncResult(selection.names, automatic_change=automatic_change)
    try:
        plan = port.prepare_plan(request, selection, settings)
    except (OSError, ValueError, RuntimeError) as error:
        port.record_failure(selection, settings, str(error))
        raise
    changed = any(
        effect.action != "UNCHANGED"
        for export in plan.exports
        for effect in export.effects
    )
    agreement_changed = port.agreement_changed(plan)
    run_uid = str(uuid4()) if changed or agreement_changed or automatic_change else None
    if run_uid:
        port.begin_publication(plan, run_uid)
    try:
        effects = tuple(
            replace(effect, path=str(export.destination / effect.path))
            for export in plan.exports
            for effect in publish_export_documents(export, port.publisher_for(export))
        )
        result = SyncResult(
            selection.names, effects, automatic_change, run_uid, request.automatic
        )
        # Publish document bytes first; only successful agreement can enable
        # automatic mode. The primary command has already committed separately.
        port.finish_publication(
            plan, settings, updated_policies, result, request.causing_command
        )
        return result
    except (OSError, ValueError, RuntimeError) as error:
        port.record_failure(selection, settings, str(error))
        raise
