"""Compatibility alias for the operation-owned Forget runtime."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.forget.runtime")
sys.modules[__name__] = _canonical
