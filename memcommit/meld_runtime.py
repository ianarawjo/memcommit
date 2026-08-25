"""Compatibility alias for the operation-owned Meld runtime."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.meld.runtime")
sys.modules[__name__] = _canonical
