"""Compatibility alias for the operation-owned Show application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.show.application")
sys.modules[__name__] = _canonical
