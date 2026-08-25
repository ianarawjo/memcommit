"""Compatibility alias for operation-owned Atomize normal-form planning."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.atomize.normal_form")
sys.modules[__name__] = _canonical
