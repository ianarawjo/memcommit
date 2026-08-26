"""Compatibility alias for the operation-owned Search module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.search.answer_dialogue")
sys.modules[__name__] = _canonical
