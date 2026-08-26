"""Compatibility alias for the operation-owned Review module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.review.report_adapters")
sys.modules[__name__] = _canonical
