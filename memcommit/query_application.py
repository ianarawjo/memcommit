"""Compatibility alias for the operation-owned ordinary Query application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.query.ordinary_application")
sys.modules[__name__] = _canonical
