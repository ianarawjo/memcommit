"""Compatibility alias for the operation-owned Atomize analysis runtime."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.atomize.analysis_runtime")
sys.modules[__name__] = _canonical
