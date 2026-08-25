"""Compatibility alias for the operation-owned Resolve runtime."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.resolve.runtime")
sys.modules[__name__] = _canonical
