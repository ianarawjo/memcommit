"""Compatibility alias for the shared infrastructure module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.infrastructure.config")
sys.modules[__name__] = _canonical
