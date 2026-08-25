"""Compatibility alias for the operation-owned Help application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.help.application")
sys.modules[__name__] = _canonical
