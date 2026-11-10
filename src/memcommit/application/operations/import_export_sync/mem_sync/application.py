"""One manual Sync, planned completely before exception-atomic publication."""

from memcommit.persistence.store import ProfileStore
from memcommit.persistence.operations.mem_sync.automatic import sync_operation_lock

from .model import SyncResult
from .publication import publish_profile_changes
from .runtime import prepare_sync_plan


def run_sync(store: ProfileStore, *, choose_conflict_version=None) -> SyncResult:
    with sync_operation_lock(store):
        project_root_dir = store.store_dir.parent
        plan = prepare_sync_plan(store, project_root_dir)
        if plan.conflicts:
            from .sync_conflict_resolution import choose_mem_or_workspace_version

            plan = choose_mem_or_workspace_version(plan, choose_conflict_version)
        result = publish_profile_changes(store, project_root_dir, plan)
        from memcommit.persistence.operations.mem_sync.automatic import read_automatic_settings

        try:
            if read_automatic_settings(store).enabled:
                from .automatic.runtime import AutomaticSyncOutcome, record_automatic_outcome

                record_automatic_outcome(store, AutomaticSyncOutcome("synced", result=result), trigger="MANUAL")
        except (OSError, ValueError, TypeError):
            # Optional scheduling metadata must not turn a completed explicit
            # Sync into a failure or prevent its receipt from reaching the user.
            pass
        return result
