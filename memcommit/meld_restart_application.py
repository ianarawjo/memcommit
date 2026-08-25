"""Compatibility alias for the operation-owned Meld restart application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.meld.restart_application")
sys.modules[__name__] = _canonical
