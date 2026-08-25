"""Compatibility alias for the operation-owned Show runtime."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.show.runtime")
sys.modules[__name__] = _canonical
