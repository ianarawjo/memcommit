"""Compatibility alias for the operation-owned Ground Fit receipt store."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.fit.store")
sys.modules[__name__] = _canonical
