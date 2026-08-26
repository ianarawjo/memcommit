"""Lazy public CLI surface for the profile command package."""

from memcommit.commands import _load_entrypoint_attribute


__all__ = ["app"]


def __getattr__(name: str):
    return _load_entrypoint_attribute(__name__, __all__, name)
