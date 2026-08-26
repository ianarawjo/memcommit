"""Compatibility alias for the operation-owned Elaborate module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.elaborate.config")
sys.modules[__name__] = _canonical
