"""Compatibility alias for the operation-owned Query module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.query.answer")
sys.modules[__name__] = _canonical
