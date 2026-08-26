"""Compatibility alias for the operation-owned Dedup module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.dedup.planning")
sys.modules[__name__] = _canonical
