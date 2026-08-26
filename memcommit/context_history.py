"""Compatibility alias for the shared retained-history module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.retained_history.context_history")
sys.modules[__name__] = _canonical
