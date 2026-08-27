"""Lazy public CLI surface for the write_protection command package."""

from memcommit.adapters.console.commands import _load_entrypoint_attribute


__all__ = ["lock_app", "unlock_app"]


def __getattr__(name: str):
    return _load_entrypoint_attribute(__name__, __all__, name)
