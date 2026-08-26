"""Compatibility alias for the operation-owned Meld module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.meld.model")
sys.modules[__name__] = _canonical
