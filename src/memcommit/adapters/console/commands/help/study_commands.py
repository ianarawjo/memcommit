"""Shared Study command names exposed through mem help."""

# Remove a canonical name here to hide its row in every Study's mem help.
# Keep this explicit: adding a command must not expose it in Study Help
# until it is deliberately included. CLI routing and completion stay independent.
STUDY_VISIBLE_COMMAND_NAMES = frozenset(
    {
        "add",
        "audit",
        "branch",
        "contexts",
        "delete",
        "edit",
        "find",
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
