"""Compatibility alias for the operation-owned Compare summary application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.compare.summary_application")
sys.modules[__name__] = _canonical
