"""One manual Sync, planned completely before exception-atomic publication."""

from .model import SyncPort, SyncRequest, SyncResult


def run_sync(
    request: SyncRequest, port: SyncPort, *, choose_conflict_version=None
) -> SyncResult:
    with port.execution_boundary():
        selection = port.freeze_selection(request)
        settings = port.settings.load()
        plan = port.prepare_plan(request, selection, settings)
        if plan.conflicts:
            from .conflict_resolution import select_conflict_version

            plan = select_conflict_version(plan, choose_conflict_version)
        return port.publish_profile_changes(plan, request, settings)
