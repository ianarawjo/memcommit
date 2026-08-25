"""Compatibility alias for the operation-owned Compare summary model."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.compare.summary")
sys.modules[__name__] = _canonical
