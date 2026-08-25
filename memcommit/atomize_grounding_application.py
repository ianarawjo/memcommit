"""Compatibility alias for operation-owned Atomize Grounding application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.atomize.grounding_application")
sys.modules[__name__] = _canonical
