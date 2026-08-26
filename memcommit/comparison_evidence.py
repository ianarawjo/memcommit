"""Compatibility alias for the operation-owned Compare module."""

from importlib import import_module
import sys


_canonical = import_module("memcommit.operations.compare.ledger.evidence")
sys.modules[__name__] = _canonical
