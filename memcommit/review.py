"""Compatibility alias for the operation-owned Review module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.review.model")
sys.modules[__name__] = _canonical
