"""Persist the current Context and Memory graph and its lifecycle."""

from __future__ import annotations

import sys
from types import ModuleType

from . import models as _models_module
from . import records as _records_module
from . import current as _current_module
from . import addressing as _addressing_module
from . import context_listing_eligibility as _context_listing_eligibility_module
from . import context_creation_availability as _context_creation_availability_module
from . import loading as _loading_module
from . import rename as _rename_module
from . import saving as _saving_module
from . import creation as _creation_module
from . import lifecycle as _lifecycle_module
from . import query_source as _query_source_module
from .addressing import _ContextAddressingMixin
from .context_listing_eligibility import _ContextListingEligibilityMixin
from .context_creation_availability import _ContextCreationAvailabilityMixin
from .loading import _ContextLoadingMixin
from .rename import _ContextRenameMixin
from .saving import _ContextSavingMixin
from .creation import _ContextCreationMixin
from .lifecycle import _ContextLifecycleMixin
from .query_source import _QuerySourceStoreMixin
from .current import _CurrentContextStoreMixin


_IMPLEMENTATION_MODULES = (
    _models_module,
    _records_module,
    _current_module,
    _addressing_module,
    _context_listing_eligibility_module,
    _context_creation_availability_module,
    _loading_module,
    _rename_module,
    _saving_module,
    _creation_module,
    _lifecycle_module,
    _query_source_module,
)


class ContextMemoryStoreMixin(
    _CurrentContextStoreMixin,
    _ContextAddressingMixin,
    _ContextListingEligibilityMixin,
    _ContextCreationAvailabilityMixin,
    _ContextLoadingMixin,
    _ContextRenameMixin,
    _ContextSavingMixin,
    _ContextCreationMixin,
    _ContextLifecycleMixin,
    _QuerySourceStoreMixin,
):
    """Compatibility surface assembled from focused persistence mixins."""


class _ContextMemoryCompatibilityModule(ModuleType):
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


__all__ = ["ContextMemoryStoreMixin"]

# The root Store compatibility module historically monkeypatches atomic-write
# helpers on this import path. Keep that behavior while the combined
# MemoryStore façade exists, but do not add new state to this adapter.
sys.modules[__name__].__class__ = _ContextMemoryCompatibilityModule
