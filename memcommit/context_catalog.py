"""Compatibility alias for the shared Context-targeting module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.context_targeting.context_catalog")
sys.modules[__name__] = _canonical
