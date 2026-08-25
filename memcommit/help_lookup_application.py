"""Compatibility alias for the operation-owned semantic Help lookup."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.help.lookup_application")
sys.modules[__name__] = _canonical
