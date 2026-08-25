"""Compatibility alias for the operation-owned Sever session Store."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.sever.session_store")
sys.modules[__name__] = _canonical
