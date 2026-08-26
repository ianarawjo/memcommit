"""Compatibility alias for the shared reviewing module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.reviewing.session_navigation")
sys.modules[__name__] = _canonical
