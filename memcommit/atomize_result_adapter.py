"""Compatibility alias for the operation-owned Atomize result adapter."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.atomize.result_adapter")
sys.modules[__name__] = _canonical
