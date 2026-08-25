"""Compatibility alias for the operation-owned Atomize resolution adapter."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.atomize.resolution_adapter")
sys.modules[__name__] = _canonical
