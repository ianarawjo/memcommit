"""Read Store and workspace inputs for one whole-Profile Sync plan."""

from pathlib import Path

from memcommit.application.operations.import_export_sync.common.context_documents import (
    load_context_documents,
)
from memcommit.application.operations.import_export_sync.common.project_documents import (
    ProjectDocumentRules,
)
from memcommit.application.operations.import_export_sync.mem_sync.documents.change_planning.plan_context_changes import (
    plan_context_changes,
)
from memcommit.persistence.import_export.source import (
    read_project_documents,
    require_regular_output_path,
)
from memcommit.persistence.operations.mem_sync.checkpoints import (
    load_last_sync_baselines,
)
from memcommit.persistence.store import ProfileStore

from .model import SyncPlan


def prepare_sync_plan(
    profile_store: ProfileStore,
    project_root_dir: Path,
) -> SyncPlan:
    """Prepare one whole-Profile plan from mem, workspace and Sync checkpoints."""
    contexts = profile_store.load_all_contexts()
    context_names = {context.name for context in contexts}
    previous_sync_baselines = load_last_sync_baselines(profile_store, contexts)
    snapshot = read_project_documents(project_root_dir)
    rules = ProjectDocumentRules(snapshot.ignore_bytes)
    for agreement in previous_sync_baselines.values():
        if not any(member["name"] in context_names for member in agreement.members):
            continue
        for path, _data in agreement.files:
            if not rules.excludes(path):
                require_regular_output_path(project_root_dir, path)
    content = load_context_documents(profile_store, contexts)
    plan = plan_context_changes(
        content=content,
        baselines=previous_sync_baselines,
        snapshot=snapshot,
    )
    return plan
