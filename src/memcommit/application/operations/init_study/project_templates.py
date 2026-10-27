"""Locate and copy prepared Study projects without rebuilding their content."""

from __future__ import annotations

from pathlib import Path
import shutil

from memcommit.application.operations.profile.config import validate_profile_name
from memcommit.application.operations.profile.model._storage import (
    ProfileError,
    StoreInspection,
    inspect_store,
)
from memcommit.persistence.operations.mem_sync.run_repository import (
    SyncRunRepository,
    sync_record_path,
)
from memcommit.persistence.store import ProfileStore
from memcommit.persistence.store.infrastructure.atomic_io import _write_json_atomic
from memcommit.persistence.store.infrastructure.storage_permissions import (
    harden_private_storage_tree,
)


STUDY_SCENARIOS_ROOT = Path(__file__).resolve().parent / "study_scenarios"


def list_study_project_roots() -> tuple[Path, ...]:
    """Use each visible child directory as one prepared Study project."""
    project_roots = []
    for project_root in sorted(
        STUDY_SCENARIOS_ROOT.iterdir(), key=lambda path: path.name.casefold()
    ):
        if project_root.name.startswith(".") or not project_root.is_dir():
            continue
        validate_profile_name(project_root.name)
        project_roots.append(project_root)
    if not project_roots:
        raise ProfileError("No prepared Study projects were found.")
    if len({project_root.name.casefold() for project_root in project_roots}) != len(
        project_roots
    ):
        raise ProfileError("Study project names must be unique ignoring case.")
    return tuple(project_roots)


def copy_study_project(
    source_project_root: Path,
    destination: Path,
    *,
    published_root: Path,
    created_at: str,
) -> StoreInspection:
    """Copy one ready project and bind its setup receipt to this Study run."""
    shutil.copytree(source_project_root, destination, symlinks=True)
    harden_private_storage_tree(destination)
    store_root = destination / ".mem"
    inspection = inspect_store(store_root)
    store = ProfileStore(root=store_root, create=False)
    for receipt in SyncRunRepository(store).history():
        if receipt.get("trigger") != "STUDY_SETUP":
            continue
        # The prepared checkpoints are store-local starting state. Only the
        # setup receipt's timestamp and project locations describe the new run.
        template_root = Path(receipt["profile"]["root"])
        receipt["profile"]["root"] = str(published_root)
        receipt["created_at"] = created_at
        for effect in receipt["effects"]:
            relative = Path(effect["path"]).relative_to(template_root)
            effect["path"] = str(published_root / relative)
        _write_json_atomic(
            sync_record_path(store, "runs", receipt["uid"] + ".json"), receipt
        )
    return inspection
