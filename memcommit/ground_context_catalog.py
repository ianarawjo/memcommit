"""Compatibility alias for the operation-owned Ground module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.ground.context_catalog")
sys.modules[__name__] = _canonical
