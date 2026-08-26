"""Authored policy for commands projected by interactive semantic workflows."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class InteractiveCommandRole(str, Enum):
    """Meaning of one command line in an interactive workflow."""

    START = "START"
    TURN = "TURN"
    RECEIPT = "RECEIPT"
    NONE = "NONE"


class InteractiveCommandBinding(str, Enum):
    """State that gives a displayed command its stable meaning."""

    PORTABLE = "PORTABLE"
    SESSION_REVISION = "SESSION_REVISION"
    NONE = "NONE"


class InteractiveCommandApproval(str, Enum):
    """How a displayed command crosses its execution boundary."""

    FOCUSED_ENTER = "FOCUSED_ENTER"
    ALREADY_SUBMITTED = "ALREADY_SUBMITTED"
    NONE = "NONE"


class InteractiveCommandRebuildTrigger(str, Enum):
    """Changes that invalidate and rebuild a displayed command."""

    DRAFT_CHANGE = "DRAFT_CHANGE"
    SESSION_REVISION = "SESSION_REVISION"


@dataclass(frozen=True)
class InteractiveCommandSurface:
    """One globally classified interactive command surface."""

    operation: str
    surface: str
    role: InteractiveCommandRole
    binding: InteractiveCommandBinding
    approval: InteractiveCommandApproval
    rebuild_on: frozenset[InteractiveCommandRebuildTrigger] = frozenset()
    note: str = ""

    def __post_init__(self) -> None:
        if (
            not self.operation
            or not self.surface
            or any(character in self.operation + self.surface for character in "\r\n")
        ):
            raise ValueError("Interactive command surfaces require stable identity.")
        if self.role is InteractiveCommandRole.NONE:
            if (
                self.binding is not InteractiveCommandBinding.NONE
                or self.approval is not InteractiveCommandApproval.NONE
                or self.rebuild_on
            ):
                raise ValueError("A NONE command surface cannot retain command state.")
            return
        if self.role is InteractiveCommandRole.START:
            if (
                self.binding is not InteractiveCommandBinding.PORTABLE
                or self.approval is not InteractiveCommandApproval.FOCUSED_ENTER
                or self.rebuild_on
                != frozenset({InteractiveCommandRebuildTrigger.DRAFT_CHANGE})
            ):
                raise ValueError(
                    "A START command must be portable, draft-rebuilt, and Enter-approved."
                )
            return
        if self.role is InteractiveCommandRole.TURN:
            if (
                self.binding is not InteractiveCommandBinding.SESSION_REVISION
                or self.approval is not InteractiveCommandApproval.FOCUSED_ENTER
                or self.rebuild_on
                != frozenset(
                    {
                        InteractiveCommandRebuildTrigger.DRAFT_CHANGE,
                        InteractiveCommandRebuildTrigger.SESSION_REVISION,
                    }
                )
            ):
                raise ValueError(
                    "A TURN command must be revision-bound and rebuilt from both draft and session state."
                )
            return
        if self.role is InteractiveCommandRole.RECEIPT and (
            self.approval is not InteractiveCommandApproval.ALREADY_SUBMITTED
            or self.rebuild_on
        ):
            raise ValueError("A RECEIPT records an already-submitted command.")

    @property
    def uid(self) -> str:
        return f"{self.operation}.{self.surface}"


_START_REBUILD = frozenset({InteractiveCommandRebuildTrigger.DRAFT_CHANGE})
_TURN_REBUILD = frozenset(
    {
        InteractiveCommandRebuildTrigger.DRAFT_CHANGE,
        InteractiveCommandRebuildTrigger.SESSION_REVISION,
    }
)


INTERACTIVE_COMMAND_SURFACES: tuple[InteractiveCommandSurface, ...] = (
    *(
        InteractiveCommandSurface(
            operation,
            "setup",
            InteractiveCommandRole.START,
            InteractiveCommandBinding.PORTABLE,
            InteractiveCommandApproval.FOCUSED_ENTER,
            _START_REBUILD,
            "The TUI composes the public command that starts or resumes analysis.",
        )
        for operation in ("meld", "update", "sever")
    ),
    *(
        InteractiveCommandSurface(
            operation,
            "semantic-turn",
            InteractiveCommandRole.TURN,
            InteractiveCommandBinding.SESSION_REVISION,
            InteractiveCommandApproval.FOCUSED_ENTER,
            _TURN_REBUILD,
            "The command is rebuilt from the staged response and exact saved revision.",
        )
        for operation in ("meld", "update", "sever")
    ),
    *(
        InteractiveCommandSurface(
            operation,
            "semantic-result",
            InteractiveCommandRole.NONE,
            InteractiveCommandBinding.NONE,
            InteractiveCommandApproval.NONE,
            note="This bounded semantic transform intentionally keeps its existing review flow.",
        )
        for operation in ("summarize", "distill", "atomize")
    ),
    *(
        InteractiveCommandSurface(
            operation,
            "final-apply",
            InteractiveCommandRole.NONE,
            InteractiveCommandBinding.NONE,
            InteractiveCommandApproval.NONE,
            note="Apply consumes the frozen reviewed session and is intentionally not another command line.",
        )
        for operation in ("meld", "update", "sever")
    ),
)


def interactive_command_surface(
    operation: str,
    surface: str,
) -> InteractiveCommandSurface:
    """Return one authored classification or fail on an unregistered boundary."""

    matches = tuple(
        item
        for item in INTERACTIVE_COMMAND_SURFACES
        if item.operation == operation and item.surface == surface
    )
    if len(matches) != 1:
        raise KeyError(f"Unknown interactive command surface: {operation}.{surface}")
    return matches[0]


def validate_interactive_command_surfaces() -> None:
    """Reject duplicate or incomplete semantic-session classifications."""

    uids = tuple(item.uid for item in INTERACTIVE_COMMAND_SURFACES)
    if len(uids) != len(set(uids)):
        raise ValueError("Interactive command surface identities must be unique.")
    for operation in ("meld", "update", "sever"):
        roles = {
            item.surface: item.role
            for item in INTERACTIVE_COMMAND_SURFACES
            if item.operation == operation
        }
        if roles != {
            "setup": InteractiveCommandRole.START,
            "semantic-turn": InteractiveCommandRole.TURN,
            "final-apply": InteractiveCommandRole.NONE,
        }:
            raise ValueError(f"{operation} has an incomplete command boundary.")


validate_interactive_command_surfaces()


__all__ = [
    "INTERACTIVE_COMMAND_SURFACES",
    "InteractiveCommandApproval",
    "InteractiveCommandBinding",
    "InteractiveCommandRebuildTrigger",
    "InteractiveCommandRole",
    "InteractiveCommandSurface",
    "interactive_command_surface",
    "validate_interactive_command_surfaces",
]
