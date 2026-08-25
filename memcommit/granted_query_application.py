"""Compatibility alias for the operation-owned granted Query application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.query.granted_application")
sys.modules[__name__] = _canonical
