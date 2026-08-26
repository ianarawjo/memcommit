"""Compatibility alias for the operation-owned Profile module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.profile.config")
sys.modules[__name__] = _canonical
