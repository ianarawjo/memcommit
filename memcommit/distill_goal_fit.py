"""Compatibility alias for the operation-owned Distill module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.distill.goal_fit")
sys.modules[__name__] = _canonical
