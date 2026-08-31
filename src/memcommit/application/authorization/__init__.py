"""Operation-neutral authorization policies for resolved application inputs."""

from .context_use import ContextUse, authorize_context_use

__all__ = ["ContextUse", "authorize_context_use"]
