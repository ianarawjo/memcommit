"""Compatibility alias for the operation-owned Reference runtime."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.reference.runtime")
sys.modules[__name__] = _canonical
