"""Compatibility alias for the operation-owned Reference module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.reference.provenance")
sys.modules[__name__] = _canonical
