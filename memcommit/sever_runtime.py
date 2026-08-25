"""Compatibility alias for the operation-owned Sever runtime."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.sever.runtime")
sys.modules[__name__] = _canonical
