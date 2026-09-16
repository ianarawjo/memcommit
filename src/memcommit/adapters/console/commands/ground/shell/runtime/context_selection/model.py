"""Typed rows shown by the blank-Ground Context selector."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from memcommit.adapters.console.commands.ground.shell.proposal import (
    GroundShellContextSuggestion,
)

GroundContextCandidateKind = Literal[
    "EXISTING",
    "NEW_SUGGESTION",
    "DIRECT_PICK",
    "ADD_NEW",
    "CONTINUE_EMPTY",
]


@dataclass(frozen=True)
class GroundContextCandidateRow:
    """One semantic cursor row in the process-local Context selector."""

    kind: GroundContextCandidateKind
    context_name: str = ""
    existing: GroundShellContextSuggestion | None = None
