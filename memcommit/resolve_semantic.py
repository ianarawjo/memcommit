"""Compatibility alias for the operation-owned Resolve module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.resolve.semantic")
sys.modules[__name__] = _canonical
