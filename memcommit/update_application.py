"""Compatibility alias for the operation-owned Update application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.update.application")
sys.modules[__name__] = _canonical
