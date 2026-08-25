"""Compatibility alias for the operation-owned primary Atomize runtime."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.atomize.runtime")
sys.modules[__name__] = _canonical
