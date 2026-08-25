"""Compatibility alias for the operation-owned Dedup runtime."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.dedup.runtime")
sys.modules[__name__] = _canonical
