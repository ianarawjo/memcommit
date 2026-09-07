"""Compatibility composition for checkpoint and command restoration."""

from __future__ import annotations

import sys
from types import ModuleType

from .checkpoint import CheckpointStoreMixin
from .checkpoint import repository as _repository_module
from .checkpoint import revert as _revert_module
from .command_restoration import CommandRestorationStoreMixin
from .command_restoration import archive as _archive_module
from .command_restoration import engine as _engine_module
from .command_restoration.handlers.atomize import restoration as _atomize_module
from .command_restoration.handlers import branch as _branch_module
from .command_restoration.handlers import (
    companion_sessions as _companion_sessions_module,
)
from .command_restoration.handlers import merge as _merge_module
from .command_restoration.handlers import sever as _sever_module


_IMPLEMENTATION_MODULES = (
    _repository_module,
    _revert_module,
    _archive_module,
    _engine_module,
    _branch_module,
    _merge_module,
    _atomize_module,
    _sever_module,
    _companion_sessions_module,
)


class RecordRestoreCheckpointStoreMixin(
    CheckpointStoreMixin,
    CommandRestorationStoreMixin,
):
    """Preserve the combined Store surface while callers migrate."""


class _RecordRestoreCheckpointCompatibilityModule(ModuleType):
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


__all__ = ["RecordRestoreCheckpointStoreMixin"]


# Preserve root Store failure-injection overrides during the façade migration.
sys.modules[__name__].__class__ = _RecordRestoreCheckpointCompatibilityModule
