"""Compatibility alias for the operation-owned Embed runtime."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.embed.runtime")
sys.modules[__name__] = _canonical
