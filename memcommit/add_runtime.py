"""Compatibility alias for the operation-owned Add runtime."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.add.runtime")
sys.modules[__name__] = _canonical
