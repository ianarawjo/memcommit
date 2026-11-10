"""Conflict directions, decision options and accepted Update instructions."""

from .accepted_direction import (
    SUGGESTION_INSTRUCTIONS as SUGGESTION_INSTRUCTIONS,
    build_resolution_choices as build_resolution_options,
    build_update_instruction as build_update_instruction,
)

__all__ = [
    "SUGGESTION_INSTRUCTIONS",
    "build_resolution_options",
    "build_update_instruction",
]
