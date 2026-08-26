"""Compatibility alias for the operation-owned Dedun module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.dedun.scope")
sys.modules[__name__] = _canonical
