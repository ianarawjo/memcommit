"""Compatibility alias for operation-owned Search materialization."""

from importlib import import_module
import sys


_canonical = import_module(
    "memcommit.operations.search.materialization_application"
)
sys.modules[__name__] = _canonical
