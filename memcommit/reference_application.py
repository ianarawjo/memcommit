"""Compatibility alias for the operation-owned Reference application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.reference.application")
sys.modules[__name__] = _canonical
