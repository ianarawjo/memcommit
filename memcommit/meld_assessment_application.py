"""Compatibility alias for the operation-owned Meld assessment application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.meld.assessment_application")
sys.modules[__name__] = _canonical
