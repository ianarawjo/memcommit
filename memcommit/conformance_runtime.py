"""Compatibility alias for the operation-owned Conformance module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.conformance.runtime")
sys.modules[__name__] = _canonical
