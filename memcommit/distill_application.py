"""Compatibility alias for the operation-owned Distill application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.distill.application")
sys.modules[__name__] = _canonical
