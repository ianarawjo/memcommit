"""Compatibility alias for operation-owned Compare summary rules."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.compare.summary_rules")
sys.modules[__name__] = _canonical
