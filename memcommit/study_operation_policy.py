"""Compatibility alias for the shared authority module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.authority.study_operation_policy")
sys.modules[__name__] = _canonical
