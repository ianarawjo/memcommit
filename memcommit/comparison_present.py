"""Compatibility alias for the operation-owned Compare module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.interfaces.cli.comparison")
sys.modules[__name__] = _canonical
