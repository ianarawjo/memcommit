"""Compatibility alias for the operation-owned Merge module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.merge.planning")
sys.modules[__name__] = _canonical
