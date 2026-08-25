"""Compatibility alias for the operation-owned Sever model."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.sever.model")
sys.modules[__name__] = _canonical
