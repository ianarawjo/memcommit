"""Compatibility alias for the shared application module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.application.review_policy")
sys.modules[__name__] = _canonical
