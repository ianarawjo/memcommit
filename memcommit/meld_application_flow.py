"""Compatibility alias for the operation-owned Meld application flow."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.meld.application_flow")
sys.modules[__name__] = _canonical
