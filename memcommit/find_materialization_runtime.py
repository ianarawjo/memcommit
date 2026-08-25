"""Compatibility alias for the operation-owned Search materialization runtime."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.search.materialization_runtime")
sys.modules[__name__] = _canonical
