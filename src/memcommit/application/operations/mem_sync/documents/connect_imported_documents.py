"""Adopt matching project files into an unpublished Profile's Sync records."""

from dataclasses import replace
from uuid import uuid4

from memcommit.application.operations.mem_sync.automatic.settings import (
    set_automatic_selection,
)
from memcommit.application.operations.mem_sync.model import SyncRequest, SyncResult
from memcommit.application.operations.mem_sync.runtime import SyncRuntime
from memcommit.persistence.import_export.source import read_output_files


def connect_imported_documents(store):
    """Use the ordinary Sync planner, allowing only byte-identical adoption.

    The caller owns this unregistered staging Store. No project writer is used:
    failure can discard staging without undoing another application's files.
    """
    runtime = SyncRuntime(store)
    with runtime.execution_boundary():
        request = SyncRequest(all_contexts=True, automatic=True)
        selection = runtime.freeze_selection(request)
        settings = runtime.settings.load()
        policies, change = set_automatic_selection(
            selection, settings["policies"], enabled=True
        )
        plan = runtime.prepare_plan(request, selection, settings)
        effects = []
        for export in plan.exports:
            if any(effect.action != "UNCHANGED" for effect in export.effects):
                raise ValueError(
                    "Project files changed during Profile setup; review creation again."
                )
            observed = read_output_files(
                export.destination, (file.path for file in export.files)
            )
            if observed != {file.path: file.data for file in export.files}:
                raise ValueError(
                    "Project files changed during Profile setup; review creation again."
                )
            effects.extend(
                replace(effect, path=str(export.destination / effect.path))
                for effect in export.effects
            )
        result = SyncResult(selection.names, tuple(effects), change, str(uuid4()))
        runtime.finish_publication(plan, settings, policies, result, "profile create")
        return result
