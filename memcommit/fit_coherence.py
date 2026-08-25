"""Compatibility alias for the operation-owned Ground Fit coherence contract."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.fit.coherence")
sys.modules[__name__] = _canonical
