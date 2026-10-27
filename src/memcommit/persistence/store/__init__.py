"""Public persistence surface composed from focused physical owners."""

# ruff: noqa: F401

import sys
from types import ModuleType

from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest

from . import context_memory as _context_memory_module
from .checkpoint import CheckpointStoreMixin
from .checkpoint import repository as _checkpoint_repository_module
from .checkpoint import revert as _checkpoint_revert_module
from .saving.command_restoration import (
    atomize as _atomize_restoration_module,
    context_creation as _branch_restoration_module,
    companion_sessions as _companion_restore_module,
    context_records as _context_restore_module,
    merge as _merge_restoration_module,
    sever as _sever_restoration_module,
)
from .context_memory import ContextStoreMixin
from .context_memory.models import (
    ConcurrentContextUpdateError,
    ContextBranchBinding,
    ContextBranchMemoryBinding,
    ContextDeletionCommittedError,
    ContextRenameBinding,
    ContextRenamePlan,
    ContextRenameResult,
)
from .context_memory.records import (
    canonical_context_record,
    checkpoint_history_digest,
    context_record_digest,
)
from .infrastructure import atomic_io as _atomic_io_module
from .infrastructure import locking as _locking_module
from .infrastructure import paths as _paths_module
from .infrastructure.atomic_io import (
    _canonical_json_digest,
    _fsync_directory,
    _reject_duplicate_json_keys,
    _write_bytes_atomic,
    _write_json_atomic,
)
from .infrastructure.locking import _StoreLockingMixin
from .infrastructure.paths import (
    ATOMIZE_ANALYSES_DIR,
    ATOMIZE_SESSION_HISTORY_DIR,
    ATOMIZE_WORKBENCHES_DIR,
    CONTEXTS_DIR,
    IMPACT_PLAN_FILE,
    REVIEW_SESSION_FILE,
    REVIEW_SESSION_HISTORY_DIR,
    REVIEW_SESSION_SOURCES_DIR,
    STAGED_UPDATE_FILE,
    STATE_FILE,
    STORE_DIR,
    _StorePathsMixin,
    resolve_active_store_dir,
)
from .loading.context_records import _ContextLoadingMixin
from .lookup.context_catalog import _ContextCatalogStoreMixin
from .lookup.context_paths import _ContextPathLookupMixin
from .lookup.command_archives import _CommandArchiveLookupMixin
from .loading.command_archives import _CommandArchiveLoadingMixin
from .saving import context_records as _saving_module
from .saving.context_records import _ContextSavingMixin

from memcommit.persistence.operations.atomize import (
    state_repository as _atomize_state_module,
)
from memcommit.persistence.operations.atomize.state_repository import (
    _AtomizeStateStoreMixin,
)
from memcommit.persistence.operations.review import (
    state_repository as _review_state_module,
)
from memcommit.persistence.operations.review.state_repository import (
    _ReviewStateStoreMixin,
)
from memcommit.persistence.operations.update import (
    receipt_repository as _update_state_module,
)
from memcommit.persistence.operations.update.receipt_repository import (
    _UpdateReceiptStoreMixin,
)


class ProfileStore(
    _StorePathsMixin,
    _StoreLockingMixin,
    _ContextPathLookupMixin,
    _ContextCatalogStoreMixin,
    _ContextLoadingMixin,
    _CommandArchiveLookupMixin,
    _CommandArchiveLoadingMixin,
    _ContextSavingMixin,
    ContextStoreMixin,
    _UpdateReceiptStoreMixin,
    _ReviewStateStoreMixin,
    _AtomizeStateStoreMixin,
    CheckpointStoreMixin,
):
    """Persist one Profile's Contexts, checkpoints, and operation records."""


_IMPLEMENTATION_MODULES = (
    _atomic_io_module,
    _paths_module,
    _locking_module,
    _update_state_module,
    _review_state_module,
    _atomize_state_module,
    _context_memory_module,
    _saving_module,
    _checkpoint_repository_module,
    _checkpoint_revert_module,
    _atomize_restoration_module,
    _branch_restoration_module,
    _companion_restore_module,
    _context_restore_module,
    _merge_restoration_module,
    _sever_restoration_module,
)

_FORWARDED_COMPATIBILITY_NAMES = frozenset(
    {
        "STORE_DIR",
        "CONTEXTS_DIR",
        "STATE_FILE",
        "IMPACT_PLAN_FILE",
        "STAGED_UPDATE_FILE",
        "REVIEW_SESSION_FILE",
        "REVIEW_SESSION_HISTORY_DIR",
        "REVIEW_SESSION_SOURCES_DIR",
        "ATOMIZE_ANALYSES_DIR",
        "ATOMIZE_WORKBENCHES_DIR",
        "ATOMIZE_SESSION_HISTORY_DIR",
        "_write_json_atomic",
        "_write_bytes_atomic",
        "_fsync_directory",
        "resolve_active_store_dir",
    }
)


class _StoreCompatibilityModule(ModuleType):
    """Keep established root-level configuration and failure injection atomic."""

    def __setattr__(self, name: str, value: object) -> None:
        super().__setattr__(name, value)
        if name not in _FORWARDED_COMPATIBILITY_NAMES:
            return
        for module in _IMPLEMENTATION_MODULES:
            if hasattr(module, name):
                setattr(module, name, value)


__all__ = [name for name in globals() if not name.startswith("_")]

sys.modules[__name__].__class__ = _StoreCompatibilityModule
