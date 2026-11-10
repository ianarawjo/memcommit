"""Provider identity capture and the plain record shared by completed reports."""

from __future__ import annotations

from .types import CompletionRun, ProviderIdentity


def provider_completion_identity(provider: object) -> ProviderIdentity | None:
    """Prefer the actual completion identity over the configured fallback."""
    last_run = getattr(provider, "last_run", None)
    if isinstance(last_run, CompletionRun):
        return last_run.identity
    identity = getattr(provider, "identity", None)
    return identity if isinstance(identity, ProviderIdentity) else None


def provider_identity_record(
    identity: ProviderIdentity | None,
) -> dict[str, str | None] | None:
    """Encode the existing six-field record; readers retain their own validation."""
    if identity is None:
        return None
    return {
        "provider": identity.provider,
        "model": identity.model,
        "model_digest": identity.model_digest,
        "runtime": identity.runtime,
        "endpoint": identity.endpoint,
        "reasoning_effort": identity.reasoning_effort,
    }
