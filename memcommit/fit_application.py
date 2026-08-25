"""Compatibility alias for the operation-owned Fit application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.fit.application")
sys.modules[__name__] = _canonical
