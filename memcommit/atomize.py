"""Compatibility alias for the operation-owned Atomize domain."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.atomize.domain")
sys.modules[__name__] = _canonical
