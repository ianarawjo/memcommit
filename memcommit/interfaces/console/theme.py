"""Shared semantic color tokens for plain and interactive terminal adapters."""

from __future__ import annotations


# Grant capability labels describe usable access in both the static catalog
# and Context pickers, so neither adapter owns a private shade.
SOURCE_CAPABILITY_HEX = "#8bd5ca"
SOURCE_CAPABILITY_RGB = (139, 213, 202)
# A rejected interaction is not a REMOVE effect even though both use the
# established red family. Keep validation presentation separately named.
ERROR_HEX = "#ed8796"
