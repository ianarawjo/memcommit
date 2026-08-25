"""Compatibility alias for the operation-owned Embed application."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.embed.application")
sys.modules[__name__] = _canonical
