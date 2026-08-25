"""Compatibility alias for the operation-owned Fit judgment contract."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.fit.judgment")
sys.modules[__name__] = _canonical
