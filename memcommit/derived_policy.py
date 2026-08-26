"""Compatibility alias for the shared authority module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.authority.derived_policy")
sys.modules[__name__] = _canonical
