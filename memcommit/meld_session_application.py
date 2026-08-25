"""Compatibility alias for the operation-owned Meld session application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.meld.session_application")
sys.modules[__name__] = _canonical
