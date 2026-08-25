"""Compatibility alias for the operation-owned Summarize application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.summarize.application")
sys.modules[__name__] = _canonical
