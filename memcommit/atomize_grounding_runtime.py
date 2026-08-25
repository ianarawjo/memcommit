"""Compatibility alias for the operation-owned Atomize Grounding runtime."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.atomize.grounding_runtime")
sys.modules[__name__] = _canonical
