"""Interactive Profile picker entry point."""

__all__ = ["choose_profile"]


def __getattr__(name: str):
    if name == "choose_profile":
        from memcommit.adapters.console.commands.profile.picker.app import (
            choose_profile,
        )

        return choose_profile
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
