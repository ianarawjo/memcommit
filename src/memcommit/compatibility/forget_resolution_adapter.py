"""Compatibility imports for the interface-owned Forget review projection."""

from memcommit.adapters.interfaces.tui.operations.forget.resolution import (
    ForgetResolutionWorkbenchAdapter,
    forget_memory_changes,
)

__all__ = ["ForgetResolutionWorkbenchAdapter", "forget_memory_changes"]
