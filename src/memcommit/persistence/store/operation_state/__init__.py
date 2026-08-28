"""Persist current selection and operation-specific working sessions."""

from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
import sys
import unicodedata
import uuid
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from pathlib import Path
from types import ModuleType
from typing import Callable, Iterable, Iterator, Optional

from memcommit.application.authority.storage_permissions import (
    ensure_private_directory,
    open_private_exclusive,
)
from memcommit.application.authority.write_protection import (
    WriteProtectionError,
    WriteProtectionRegistry,
    WriteProtectionRegistryError,
    WriteProtectionState,
)
from memcommit.application.retained_history.checkpoint_frames import (
    map_restorable_checkpoint_frames,
)
from memcommit.application.retained_history.context_lifecycle import (
    ContextLifecycleEvent,
)
from memcommit.core.context import AutoCheckpoint, Context, Memory, MemoryRef
from memcommit.core.context_targeting.naming import RESERVED_CONTEXT_SEGMENTS
from memcommit.core.context_targeting.navigation import (
    ContextNavigationDirection,
    apply_context_navigation,
    context_navigation_target,
    record_current_context_transition,
)

from ..context_memory import models as _context_models_module
from ..context_memory import records as _context_records_module
from ..context_memory.models import (
    ConcurrentContextUpdateError,
    ContextBranchBinding,
    ContextBranchMemoryBinding,
    ContextDeletionCommittedError,
    ContextRenameBinding,
    ContextRenamePlan,
    ContextRenameResult,
)
from ..context_memory.query_source import QuerySource, QuerySourceEntry
from ..context_memory.records import (
    canonical_context_record,
    checkpoint_history_digest,
    context_record_digest,
    validate_context_name,
)
from ..infrastructure import atomic_io as _atomic_io_module
from ..infrastructure import locking as _locking_module
from ..infrastructure import paths as _paths_module
from ..infrastructure import protection as _protection_module
from ..infrastructure.locking import _StoreLockingMixin
from ..infrastructure.paths import (
    ATOMIZE_ANALYSES_DIR,
    ATOMIZE_GROUNDING_HISTORY_DIR,
    ATOMIZE_GROUNDING_SESSIONS_DIR,
    ATOMIZE_SESSION_HISTORY_DIR,
    ATOMIZE_WORKBENCHES_DIR,
    CONTEXTS_DIR,
    GROUND_SESSIONS_DIR,
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
from ..infrastructure.protection import _WriteProtectionStoreMixin
from . import atomize as _atomize_module
from . import current as _current_module
from . import ground as _ground_module
from . import meld as _meld_module
from . import review as _review_module
from . import update as _update_module
from .atomize import _AtomizeStateStoreMixin
from .current import _CurrentStateStoreMixin
from .ground import (
    ConcurrentGroundUpdateError,
    _GroundStateStoreMixin,
    ground_session_record_digest,
)
from .meld import _MeldStateStoreMixin
from .review import _ReviewStateStoreMixin
from .update import _UpdateStateStoreMixin


_IMPLEMENTATION_MODULES = (
    _atomic_io_module,
    _context_models_module,
    _context_records_module,
    _paths_module,
    _protection_module,
    _locking_module,
    _current_module,
    _update_module,
    _review_module,
    _ground_module,
    _meld_module,
    _atomize_module,
)


class OperationStateStoreMixin(
    _StorePathsMixin,
    _WriteProtectionStoreMixin,
    _StoreLockingMixin,
    _CurrentStateStoreMixin,
    _UpdateStateStoreMixin,
    _ReviewStateStoreMixin,
    _GroundStateStoreMixin,
    _MeldStateStoreMixin,
    _AtomizeStateStoreMixin,
):
    """Compatibility surface assembled from infrastructure and session owners."""


class _OperationStateCompatibilityModule(ModuleType):
    """Forward historical module-global overrides to defining submodules."""

    def __getattr__(self, name: str):
        for module in _IMPLEMENTATION_MODULES:
            if hasattr(module, name):
                return getattr(module, name)
        raise AttributeError(f"module {self.__name__!r} has no attribute {name!r}")

    def __setattr__(self, name: str, value: object) -> None:
        super().__setattr__(name, value)
        for module in _IMPLEMENTATION_MODULES:
            if hasattr(module, name):
                setattr(module, name, value)


__all__ = [
    "ATOMIZE_ANALYSES_DIR",
    "ATOMIZE_GROUNDING_HISTORY_DIR",
    "ATOMIZE_GROUNDING_SESSIONS_DIR",
    "ATOMIZE_SESSION_HISTORY_DIR",
    "ATOMIZE_WORKBENCHES_DIR",
    "AutoCheckpoint",
    "CONTEXTS_DIR",
    "Callable",
    "ConcurrentContextUpdateError",
    "ConcurrentGroundUpdateError",
    "ContextBranchBinding",
    "ContextBranchMemoryBinding",
    "ContextDeletionCommittedError",
    "Context",
    "ContextLifecycleEvent",
    "ContextNavigationDirection",
    "ContextRenameBinding",
    "ContextRenamePlan",
    "ContextRenameResult",
    "ExitStack",
    "GROUND_SESSIONS_DIR",
    "IMPACT_PLAN_FILE",
    "Iterable",
    "Iterator",
    "MELD_SESSIONS_DIR",
    "MELD_SESSION_HISTORY_DIR",
    "Memory",
    "MemoryRef",
    "OperationStateStoreMixin",
    "Optional",
    "Path",
    "QUERY_SOURCES_DIR",
    "QuerySource",
    "QuerySourceEntry",
    "REVIEW_SESSION_FILE",
    "REVIEW_SESSION_HISTORY_DIR",
    "REVIEW_SESSION_SOURCES_DIR",
    "RESERVED_CONTEXT_SEGMENTS",
    "STAGED_UPDATE_FILE",
    "STATE_FILE",
    "STORE_DIR",
    "WriteProtectionError",
    "WriteProtectionRegistry",
    "WriteProtectionRegistryError",
    "WriteProtectionState",
    "annotations",
    "apply_context_navigation",
    "canonical_context_record",
    "checkpoint_history_digest",
    "context_navigation_target",
    "context_record_digest",
    "contextmanager",
    "copy",
    "dataclass",
    "datetime",
    "ensure_private_directory",
    "fcntl",
    "ground_session_record_digest",
    "hashlib",
    "json",
    "map_restorable_checkpoint_frames",
    "open_private_exclusive",
    "os",
    "record_current_context_transition",
    "validate_context_name",
    "resolve_active_store_dir",
    "unicodedata",
    "uuid",
    "wraps",
]


# Preserve the historical override surface while the combined MemoryStore exists.
sys.modules[__name__].__class__ = _OperationStateCompatibilityModule
