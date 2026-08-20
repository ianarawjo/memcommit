"""One semantic palette for plain and interactive terminal adapters.

The values in this module are intentionally independent of Typer and
prompt-toolkit. Console and TUI adapters may choose different mechanics, but
the same semantic role must resolve to the same color in both environments.
"""

from __future__ import annotations

from enum import Enum


# Palette values are named once here so an operation adapter never owns a raw
# terminal color. They retain the repository's established Macchiato-like
# palette plus the brighter blue already reserved for keyboard focus.
BACKGROUND_HEX = "#24273a"
FOCUS_TEXT_HEX = "#10242f"
FOCUS_HEX = "#8bd5ff"
REPORT_HEX = "#f4f5f7"
DETAIL_HEX = "#ffffff"
MEMORY_HEX = "#cad3f5"
PLACEHOLDER_HEX = "#a5adcb"
HISTORY_HEX = "#c9ad93"
BLUE_HEX = "#8aadf4"
GREEN_HEX = "#a6da95"
RED_HEX = "#ed8796"
PEACH_HEX = "#f5a97f"
YELLOW_HEX = "#eed49f"
MAUVE_HEX = "#c6a0f6"
TEAL_HEX = "#8bd5ca"
LAVENDER_HEX = "#b7bdf8"


class SemanticColorRole(str, Enum):
    """Stable terminal meaning shared by reports, history, and source rows."""

    CREATE = "create"
    ADD = "add"
    EMBED = "embed"
    EDIT = "edit"
    REMOVE = "remove"
    UNDO = "undo"
    REDO = "redo"
    HISTORY = "history"
    GRANT = "grant"
    NAVIGATION_GRANT = "navigation-grant"
    CAPABILITY = "capability"
    REFERENCE = "reference"


SEMANTIC_COLOR_HEX = {
    SemanticColorRole.CREATE: BLUE_HEX,
    SemanticColorRole.ADD: BLUE_HEX,
    SemanticColorRole.EMBED: YELLOW_HEX,
    SemanticColorRole.EDIT: GREEN_HEX,
    SemanticColorRole.REMOVE: RED_HEX,
    SemanticColorRole.UNDO: PEACH_HEX,
    SemanticColorRole.REDO: LAVENDER_HEX,
    SemanticColorRole.HISTORY: HISTORY_HEX,
    SemanticColorRole.GRANT: REPORT_HEX,
    SemanticColorRole.NAVIGATION_GRANT: GREEN_HEX,
    SemanticColorRole.CAPABILITY: TEAL_HEX,
    SemanticColorRole.REFERENCE: MAUVE_HEX,
}


_ACTION_ROLES = {
    "create": SemanticColorRole.CREATE,
    "created": SemanticColorRole.CREATE,
    "init": SemanticColorRole.CREATE,
    "branch": SemanticColorRole.CREATE,
    "add": SemanticColorRole.ADD,
    "added": SemanticColorRole.ADD,
    "embed": SemanticColorRole.EMBED,
    "embedded": SemanticColorRole.EMBED,
    "edit": SemanticColorRole.EDIT,
    "edited": SemanticColorRole.EDIT,
    "replace": SemanticColorRole.EDIT,
    "remove": SemanticColorRole.REMOVE,
    "removed": SemanticColorRole.REMOVE,
    "delete": SemanticColorRole.REMOVE,
    "deleted": SemanticColorRole.REMOVE,
    "clear": SemanticColorRole.REMOVE,
    "undo": SemanticColorRole.UNDO,
    "revert": SemanticColorRole.UNDO,
    "restored": SemanticColorRole.UNDO,
    "redo": SemanticColorRole.REDO,
    "redone": SemanticColorRole.REDO,
    "checkpoint": SemanticColorRole.HISTORY,
    "memory-version": SemanticColorRole.HISTORY,
    "reference": SemanticColorRole.REFERENCE,
}


def semantic_action_role(value: str) -> SemanticColorRole | None:
    """Classify one visible command/effect label without parsing report prose.

    Compound Trace labels begin with their primary ``mem`` command. Mixed
    semantic commands such as Update, Meld, and Atomize deliberately remain
    unclassified: their child ADD/EDIT/REMOVE effects own the actionable color.
    """

    if not isinstance(value, str):
        raise TypeError("Semantic action labels must be text.")
    normalized = value.strip().casefold().replace("_", "-")
    if normalized.startswith("mem "):
        normalized = normalized[4:]
    primary = normalized.split(maxsplit=1)[0] if normalized else ""
    primary = primary.split("/", 1)[0]
    return _ACTION_ROLES.get(primary)


def semantic_color_hex(role: SemanticColorRole) -> str:
    """Return the canonical hexadecimal foreground for one semantic role."""

    if not isinstance(role, SemanticColorRole):
        raise TypeError("Terminal colors require a SemanticColorRole.")
    return SEMANTIC_COLOR_HEX[role]


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    red, green, blue = (int(value[index : index + 2], 16) for index in (1, 3, 5))
    return red, green, blue


def semantic_color_rgb(role: SemanticColorRole) -> tuple[int, int, int]:
    """Return the canonical true-color tuple accepted by Click/Typer."""

    return _hex_to_rgb(semantic_color_hex(role))


# Compatibility aliases keep the in-flight compact Context catalog refactor
# source-compatible while making the semantic owner explicit above.
SOURCE_CAPABILITY_HEX = semantic_color_hex(SemanticColorRole.CAPABILITY)
SOURCE_CAPABILITY_RGB = semantic_color_rgb(SemanticColorRole.CAPABILITY)
# Validation errors are not REMOVE effects even though both use the established
# red family. Keep a separate presentation token so adapters do not mislabel a
# rejected interaction as a destructive operation.
ERROR_HEX = RED_HEX
