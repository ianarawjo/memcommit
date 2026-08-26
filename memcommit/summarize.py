"""Compatibility alias for the operation-owned Summarize module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.summarize.model")
sys.modules[__name__] = _canonical
