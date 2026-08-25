"""Compatibility alias for the operation-owned Meld start application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.meld.start_application")
sys.modules[__name__] = _canonical
