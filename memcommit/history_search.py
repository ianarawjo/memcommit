"""Compatibility alias for the operation-owned Log search module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.log.search")
sys.modules[__name__] = _canonical
