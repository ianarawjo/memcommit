"""Compatibility alias for the operation-owned granted Query runtime."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.query.granted_runtime")
sys.modules[__name__] = _canonical
