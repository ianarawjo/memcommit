"""Compatibility alias for operation-owned Literal Find application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.find.literal_application")
sys.modules[__name__] = _canonical
