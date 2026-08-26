"""Compatibility alias for the operation-owned Forget module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.forget.review")
sys.modules[__name__] = _canonical
