"""Resolve removed flat modules to their canonical owners lazily."""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import importlib.util
from importlib import import_module
from types import MappingProxyType, ModuleType
import sys
from typing import Any

from memcommit.compatibility._legacy_alias_map import (
    LEGACY_SUBMODULE_ALIASES as _GENERATED_LEGACY_SUBMODULE_ALIASES,
)
from memcommit.compatibility._legacy_command_alias_map import (
    LEGACY_COMMAND_SUBMODULE_ALIASES as _GENERATED_LEGACY_COMMAND_SUBMODULE_ALIASES,
)


LEGACY_SUBMODULE_ALIASES = MappingProxyType(_GENERATED_LEGACY_SUBMODULE_ALIASES)
LEGACY_COMMAND_SUBMODULE_ALIASES = MappingProxyType(
    _GENERATED_LEGACY_COMMAND_SUBMODULE_ALIASES
)
_ALL_LEGACY_SUBMODULE_ALIASES = {
    **LEGACY_SUBMODULE_ALIASES,
    **LEGACY_COMMAND_SUBMODULE_ALIASES,
}


_FINDER_MARKER = "memcommit-legacy-submodule-aliases-v1"
_CANONICAL_METADATA = (
    "__spec__",
    "__loader__",
    "__package__",
    "__file__",
    "__cached__",
)


class _LegacySubmoduleLoader(importlib.abc.Loader):
    """Return one canonical module without changing its import identity."""

    def __init__(self, legacy_name: str, canonical_name: str) -> None:
        self.legacy_name = legacy_name
        self.canonical_name = canonical_name
        self._canonical_metadata: dict[str, Any] = {}

    def create_module(self, spec: object) -> ModuleType:
        module = import_module(self.canonical_name)
        self._canonical_metadata = {
            name: getattr(module, name)
            for name in _CANONICAL_METADATA
            if hasattr(module, name)
        }
        return module

    def exec_module(self, module: ModuleType) -> None:
        # Import machinery temporarily projects the legacy spec onto a module
        # returned by create_module. Restore the canonical metadata so reload,
        # tracebacks, introspection, and serialized globals keep one owner.
        for name, value in self._canonical_metadata.items():
            setattr(module, name, value)


class _LegacySubmoduleFinder(importlib.abc.MetaPathFinder):
    """Recognize only the frozen historical submodule catalogs."""

    marker = _FINDER_MARKER

    def find_spec(
        self,
        fullname: str,
        path: object = None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        canonical_name = _ALL_LEGACY_SUBMODULE_ALIASES.get(fullname)
        if canonical_name is None:
            return None
        loader = _LegacySubmoduleLoader(fullname, canonical_name)
        return importlib.util.spec_from_loader(fullname, loader)


def install_legacy_submodule_aliases() -> None:
    """Install the one process-local compatibility finder idempotently."""

    if any(
        getattr(finder, "marker", None) == _FINDER_MARKER for finder in sys.meta_path
    ):
        return
    # The catalog is exact, so checking it before PathFinder avoids creating
    # one physical facade per historical name without intercepting any other
    # package or third-party import.
    sys.meta_path.insert(0, _LegacySubmoduleFinder())


__all__ = [
    "LEGACY_COMMAND_SUBMODULE_ALIASES",
    "LEGACY_SUBMODULE_ALIASES",
    "install_legacy_submodule_aliases",
]
