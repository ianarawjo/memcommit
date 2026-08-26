"""Compatibility alias for the shared semantic module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.semantic.classification.gates")
sys.modules[__name__] = _canonical
