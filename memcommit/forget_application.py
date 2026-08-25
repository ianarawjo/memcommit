"""Compatibility alias for the operation-owned Forget application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.forget.application")
sys.modules[__name__] = _canonical
