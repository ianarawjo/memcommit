"""Compatibility alias for the operation-owned Resolve application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.resolve.application")
sys.modules[__name__] = _canonical
