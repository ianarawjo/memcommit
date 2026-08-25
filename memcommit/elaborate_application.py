"""Compatibility alias for the operation-owned Elaborate application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.elaborate.application")
sys.modules[__name__] = _canonical
