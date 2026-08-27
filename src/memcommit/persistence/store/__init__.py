"""Public persistence boundary assembled from three transitional Store slices."""

import sys
from types import ModuleType

from . import context_memory as _context_memory_module
from . import operation_state as _operation_state_module
from . import record_restore_checkpoint as _checkpoint_module
from .operation_state import *  # noqa: F403
from .operation_state import (
    _canonical_json_digest,
    _fsync_directory,
    _reject_duplicate_json_keys,
    _rewrite_checkpoint_record,
    _write_bytes_atomic,
    _write_json_atomic,
)
from .context_memory import ContextMemoryStoreMixin
from .operation_state import OperationStateStoreMixin
from .record_restore_checkpoint import RecordRestoreCheckpointStoreMixin


class MemoryStore(
    OperationStateStoreMixin,
    ContextMemoryStoreMixin,
    RecordRestoreCheckpointStoreMixin,
):
    """Compatibility Store surface while callers migrate to narrower owners.

    The three bases preserve the established cross-slice ``self`` calls during
    the first mechanical extraction. New persistence behavior must not be added
    here; this assembly is deleted after callers depend on the final components.
    """


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
        "ATOMIZE_GROUNDING_SESSIONS_DIR",
        "ATOMIZE_GROUNDING_HISTORY_DIR",
        "GROUND_SESSIONS_DIR",
        "MELD_SESSIONS_DIR",
        "MELD_SESSION_HISTORY_DIR",
        "_write_json_atomic",
        "_write_bytes_atomic",
        "_fsync_directory",
        "resolve_active_store_dir",
    }
)


class _StoreCompatibilityModule(ModuleType):
    """Forward legacy test/configuration overrides to each extracted owner.

    Existing callers historically replaced a few module globals on
    ``memcommit.persistence.store``. Methods now resolve globals in their defining slice,
    so the temporary compatibility boundary must keep those overrides atomic
    across all three modules until callers stop mutating the root surface.
    """

    def __setattr__(self, name: str, value: object) -> None:
        super().__setattr__(name, value)
        if name not in _FORWARDED_COMPATIBILITY_NAMES:
            return
        for module in (
            _operation_state_module,
            _context_memory_module,
            _checkpoint_module,
        ):
            if hasattr(module, name):
                setattr(module, name, value)


__all__ = [
    name
    for name in globals()
    if not name.startswith("_")
]

# Keep the established root-module mutation behavior during this first split.
# This module class disappears with the MemoryStore compatibility assembly.
sys.modules[__name__].__class__ = _StoreCompatibilityModule
