"""Lazy public CLI surface for the literal_find command package."""

from memcommit.commands import _load_entrypoint_attribute


__all__ = ["cmd"]


def __getattr__(name: str):
    return _load_entrypoint_attribute(__name__, __all__, name)
