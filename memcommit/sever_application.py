"""Compatibility alias for the operation-owned Sever application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.sever.application")
sys.modules[__name__] = _canonical
