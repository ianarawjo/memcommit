"""Coordinate first-use readiness without owning provider configuration."""

from memcommit.configuration.config import Config
from memcommit.llm_providers.types import SEMANTIC_PROVIDER_IDS

def needs_provider_setup() -> bool:
    """Check saved defaults without contacting a provider or assuming Codex was chosen."""
    config = Config()
    # The Config accessor falls back to Codex even before a person selects it.
    provider_id = config.get("semantic_provider")
    if provider_id not in SEMANTIC_PROVIDER_IDS:
        return True
    model = config.model_for_provider(provider_id)
    return not isinstance(model, str) or not model.strip()


def needs_first_profile() -> bool:
    """Keep registered Profiles and physical legacy authoring data in place."""
    from memcommit.application.operations.profile.config import (
        default_store_dir,
        profile_registry_file,
    )

    store_dir = default_store_dir()
    return (
        not profile_registry_file().exists()
        and not store_dir.exists()
        and not store_dir.is_symlink()
    )


def initial_setup_needed() -> bool:
    """Enter setup when either provider defaults or a first Profile is missing."""
    return needs_provider_setup() or needs_first_profile()
