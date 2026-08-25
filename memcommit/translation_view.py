"""Compatibility alias for the operation-owned Translate view model."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.translate.view")
sys.modules[__name__] = _canonical
