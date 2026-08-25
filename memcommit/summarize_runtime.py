"""Compatibility alias for the operation-owned Summarize runtime."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.summarize.runtime")
sys.modules[__name__] = _canonical
