"""Compatibility alias for the operation-owned Chunk domain."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.chunk.domain")
sys.modules[__name__] = _canonical
