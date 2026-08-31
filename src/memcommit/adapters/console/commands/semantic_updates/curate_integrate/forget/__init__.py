"""Lazy public CLI surface for the semantic_updates.curate_integrate.forget command package."""

from memcommit.adapters.console.commands import _load_entrypoint_attribute


__all__ = ["cmd"]


def __getattr__(name: str):
    return _load_entrypoint_attribute(__name__, __all__, name)
