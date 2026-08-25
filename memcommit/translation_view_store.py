"""Compatibility alias for the operation-owned Translate view store."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.translate.view_store")
sys.modules[__name__] = _canonical
