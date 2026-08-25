"""Compatibility alias for the operation-owned Ground Fit report contract."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.fit.ground_report")
sys.modules[__name__] = _canonical
