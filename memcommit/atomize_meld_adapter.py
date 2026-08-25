"""Compatibility alias for the operation-owned grounding Meld adapter."""

from importlib import import_module
import sys


_canonical = import_module(
    "memcommit.operations.atomize.grounding_meld_adapter"
)
sys.modules[__name__] = _canonical
