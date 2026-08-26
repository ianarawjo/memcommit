"""Compatibility alias for the operation-owned resource Import module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.resource_import.model")
sys.modules[__name__] = _canonical
