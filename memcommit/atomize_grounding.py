"""Compatibility alias for the operation-owned Atomize grounding model."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.atomize.grounding")
sys.modules[__name__] = _canonical
