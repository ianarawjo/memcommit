"""Lazy public CLI surface for the semantic_eval command package."""

from memcommit.commands import _load_entrypoint_attribute


__all__ = ["eval_app"]


def __getattr__(name: str):
    return _load_entrypoint_attribute(__name__, __all__, name)
