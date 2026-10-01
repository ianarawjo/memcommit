"""Relocate all workspace data before changing its bootstrap configuration."""

import os
from pathlib import Path

from memcommit.configuration.workspace import (
    WorkspaceError,
    canonical_workspace,
    config_file,
    configuration_lock,
    ensure_workspace,
    legacy_locations,
    needs_legacy_migration,
    read_configuration,
    workspace_lock,
    workspace_paths,
    write_configuration,
)
from memcommit.persistence.workspace import copied_workspace


def relocate_workspace(value: str) -> Path:
    if "MEMCOMMIT_WORKSPACE_DIR" in os.environ:
        raise WorkspaceError(
            "Unset MEMCOMMIT_WORKSPACE_DIR before changing the saved workspace_dir."
        )
    destination = canonical_workspace(value)
    if config_file().resolve().is_relative_to(destination):
        raise WorkspaceError(
            "The configuration file must remain outside the workspace."
        )
    with workspace_lock(exclusive=True), configuration_lock():
        bootstrap = read_configuration()
        settings = {
            key: value for key, value in bootstrap.items() if key != "workspace_dir"
        }
        legacy = needs_legacy_migration()
        current = workspace_paths().workspace_dir
        if not legacy:
            settings.update(read_configuration(current / ".mem/config.json"))
        if not legacy and current == destination:
            ensure_workspace()
            write_configuration(settings, destination / ".mem/config.json")
            write_configuration({"workspace_dir": str(destination)})
            return destination
        if legacy:
            authoring, profiles = legacy_locations()
            # Preserve existing provider settings while retaining untouched originals.
            settings = {**read_configuration(authoring / "config.json"), **settings}
            settings.pop("workspace_dir", None)
            sources = ((authoring, ".mem/authoring"), (profiles, ".mem/profiles"))
        else:
            sources = ((current, "."),)
        with copied_workspace(destination, sources):
            write_configuration(settings, destination / ".mem/config.json")
            write_configuration({"workspace_dir": str(destination)})
        return destination
