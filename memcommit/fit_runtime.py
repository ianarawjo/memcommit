"""Compatibility alias for the operation-owned Fit runtime."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.fit.runtime")
sys.modules[__name__] = _canonical
