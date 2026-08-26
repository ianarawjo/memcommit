"""Compatibility alias for the canonical shared module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.architecture.catalog")
sys.modules[__name__] = _canonical
