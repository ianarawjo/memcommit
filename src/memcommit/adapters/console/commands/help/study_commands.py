"""Study Profile detection and command names for Help and spelling suggestions."""

from memcommit.application.operations.profile.config import (
    load_profile_registry,
    study_run_identity,
)

# Remove a canonical name here to hide its row in every Study's mem help.
# Keep this explicit: adding a command must not expose it in Study Help
# until it is deliberately included. CLI routing and completion stay independent.
# Root spelling suggestions use the same set to preserve that discovery boundary.
STUDY_VISIBLE_COMMAND_NAMES = frozenset(
    {
        "add",
        "branch",
        "contexts",
        "dedup",
        "delete",
        "edit",
        "find",
        "forget",
        "help",
        "init",
        "list",
        "merge",
        "profile",
        "pwd",
        "query",
        "redo",
        "resolve",
        "switch",
        "sync",
        "undo",
        "update",
    }
)


def active_profile_is_study() -> bool:
    """Use immutable init-study provenance, never a display-name heuristic."""

    registry = load_profile_registry()
    return study_run_identity(registry.active) is not None
