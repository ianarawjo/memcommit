"""Compatibility alias for the shared Review report contract."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.reviewing.report")
sys.modules[__name__] = _canonical
