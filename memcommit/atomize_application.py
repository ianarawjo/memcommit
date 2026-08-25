"""Compatibility alias for the operation-owned primary Atomize application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.atomize.application")
sys.modules[__name__] = _canonical
