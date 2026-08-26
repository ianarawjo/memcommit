"""Compatibility alias for the operation-owned Rationale module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.rationale.semantic")
sys.modules[__name__] = _canonical
