"""Compatibility alias for the operation-owned QueryContextRef application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.query.reference_application")
sys.modules[__name__] = _canonical
