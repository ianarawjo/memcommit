"""Compatibility alias for the operation-owned Sever resolution adapter."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.sever.resolution_adapter")
sys.modules[__name__] = _canonical
