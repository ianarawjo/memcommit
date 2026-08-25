"""Compatibility alias for the operation-owned exact Dedup application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.exact_dedup.application")
sys.modules[__name__] = _canonical
