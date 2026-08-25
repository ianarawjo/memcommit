"""Compatibility alias for the operation-owned Meld resolution application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.meld.resolution_application")
sys.modules[__name__] = _canonical
