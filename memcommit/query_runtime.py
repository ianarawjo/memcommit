"""Compatibility alias for the operation-owned ordinary Query runtime."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.query.ordinary_runtime")
sys.modules[__name__] = _canonical
