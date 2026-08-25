"""Compatibility alias for operation-owned Atomize analysis application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.atomize.analysis_application")
sys.modules[__name__] = _canonical
