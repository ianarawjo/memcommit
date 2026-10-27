"""One manual Sync, planned completely before exception-atomic publication."""

from memcommit.persistence.store import ProfileStore

from .model import SyncResult
from .publication import publish_profile_changes
from .runtime import prepare_sync_plan


def run_sync(store: ProfileStore, *, choose_conflict_version=None) -> SyncResult:
    project_root_dir = store.store_dir.parent
    plan = prepare_sync_plan(store, project_root_dir)
    if plan.conflicts:
        from .sync_conflict_resolution import choose_mem_or_workspace_version

        plan = choose_mem_or_workspace_version(plan, choose_conflict_version)
    return publish_profile_changes(
        store,
        project_root_dir,
        plan,
    )
