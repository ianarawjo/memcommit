"""Compatibility alias for the operation-owned Literal Find runtime."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.find.literal_runtime")
sys.modules[__name__] = _canonical
