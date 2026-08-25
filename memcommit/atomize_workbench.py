"""Compatibility alias for the operation-owned Atomize workbench state."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.atomize.workbench")
sys.modules[__name__] = _canonical
