"""Compatibility alias for the operation-owned Add semantic runtime."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.add.semantic_runtime")
sys.modules[__name__] = _canonical
