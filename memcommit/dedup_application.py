"""Compatibility alias for the operation-owned Dedup application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.dedup.application")
sys.modules[__name__] = _canonical
