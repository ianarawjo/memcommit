"""Resolve the active Profile registry for Store-backed public operations."""

from __future__ import annotations

from memcommit.adapters.python_api._runtime import ClientRuntime
from memcommit.adapters.python_api._support.errors import raise_public
from memcommit.adapters.python_api.errors import (
    SemanticAuthorityError,
    SemanticStorageError,
)
from memcommit.application.operations.profile.config import (
    ProfileConfigError,
    ProfileRegistry,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.application.operations.profile.model import ProfileError


def active_profile_registry(runtime: ClientRuntime) -> ProfileRegistry | None:
    """Return the live registry only when it owns this client runtime."""

    if runtime.registry is None or runtime.profile is None:
        return None
    try:
        registry = load_profile_registry()
        if (
            runtime.profile.uid == registry.active.uid
            and runtime.store_root == profile_store_dir(registry.active).resolve()
        ):
            return registry
        return None
    except (ProfileConfigError, ProfileError) as error:
        raise_public(SemanticAuthorityError, error)
    except OSError as error:
        raise_public(SemanticStorageError, error)


__all__ = ["active_profile_registry"]
