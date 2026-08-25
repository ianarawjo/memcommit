"""Compatibility alias for the operation-owned Sever provider contract."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.sever.provider")
sys.modules[__name__] = _canonical
