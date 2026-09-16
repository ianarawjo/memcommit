"""Public persistence surface composed from focused physical owners."""

# ruff: noqa: F401

import sys
from types import ModuleType

from memcommit.core.context import AutoCheckpoint

from . import context_memory as _context_memory_module
from . import record_restore_checkpoint as _checkpoint_module
from .context_memory import ContextMemoryStoreMixin
from .context_memory.models import (
    ConcurrentContextUpdateError,
    ContextBranchBinding,
    ContextBranchMemoryBinding,
    ContextDeletionCommittedError,
    ContextRenameBinding,
    ContextRenamePlan,
    ContextRenameResult,
)
from .context_memory.query_source import QuerySource, QuerySourceEntry
from .context_memory.records import (
    _rewrite_checkpoint_record,
    canonical_context_record,
    checkpoint_history_digest,
    context_record_digest,
    validate_context_name,
)
from .infrastructure import atomic_io as _atomic_io_module
from .infrastructure import locking as _locking_module
from .infrastructure import paths as _paths_module
from .infrastructure import protection as _protection_module
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
    MELD_SESSIONS_DIR,
    MELD_SESSION_HISTORY_DIR,
    QUERY_SOURCES_DIR,
    REVIEW_SESSION_FILE,
    REVIEW_SESSION_HISTORY_DIR,
    REVIEW_SESSION_SOURCES_DIR,
    STAGED_UPDATE_FILE,
    STATE_FILE,
    STORE_DIR,
    _StorePathsMixin,
    resolve_active_store_dir,
)
from .infrastructure.protection import _WriteProtectionStoreMixin
from .record_restore_checkpoint import RecordRestoreCheckpointStoreMixin

from memcommit.persistence.operations.atomize import (
    state_repository as _atomize_state_module,
)
from memcommit.persistence.operations.atomize.state_repository import (
    _AtomizeStateStoreMixin,
)
from memcommit.persistence.operations.meld import state_repository as _meld_state_module
from memcommit.persistence.operations.meld.state_repository import _MeldStateStoreMixin
from memcommit.persistence.operations.review import (
    state_repository as _review_state_module,
)
from memcommit.persistence.operations.review.state_repository import (
    _ReviewStateStoreMixin,
)
from memcommit.persistence.operations.update import (
    state_repository as _update_state_module,
)
from memcommit.persistence.operations.update.state_repository import (
    _UpdateStateStoreMixin,
)


class MemoryStore(
    _StorePathsMixin,
    _WriteProtectionStoreMixin,
    _StoreLockingMixin,
    ContextMemoryStoreMixin,
    _UpdateStateStoreMixin,
    _ReviewStateStoreMixin,
    _MeldStateStoreMixin,
    _AtomizeStateStoreMixin,
    RecordRestoreCheckpointStoreMixin,
):
    """Compose Context persistence and operation-owned repositories."""


_IMPLEMENTATION_MODULES = (
    _atomic_io_module,
    _paths_module,
    _protection_module,
    _locking_module,
    _update_state_module,
    _review_state_module,
    _meld_state_module,
    _atomize_state_module,
    _context_memory_module,
    _checkpoint_module,
)

_FORWARDED_COMPATIBILITY_NAMES = frozenset(
    {
        "STORE_DIR",
        "CONTEXTS_DIR",
        "STATE_FILE",
        "QUERY_SOURCES_DIR",
        "IMPACT_PLAN_FILE",
        "STAGED_UPDATE_FILE",
        "REVIEW_SESSION_FILE",
        "REVIEW_SESSION_HISTORY_DIR",
        "REVIEW_SESSION_SOURCES_DIR",
        "ATOMIZE_ANALYSES_DIR",
        "ATOMIZE_WORKBENCHES_DIR",
        "ATOMIZE_SESSION_HISTORY_DIR",
        "MELD_SESSIONS_DIR",
        "MELD_SESSION_HISTORY_DIR",
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
