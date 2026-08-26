"""Compatibility alias for the operation-owned Update module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.update.granted_source_application")
sys.modules[__name__] = _canonical
