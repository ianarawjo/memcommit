"""Compatibility alias for the operation-owned Translate runtime."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.translate.runtime")
sys.modules[__name__] = _canonical
