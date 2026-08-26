"""Compatibility alias for the operation-owned Share module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.share.model")
sys.modules[__name__] = _canonical
