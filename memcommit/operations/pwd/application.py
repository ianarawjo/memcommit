"""Terminal-independent application contract for current Context orientation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class CurrentContextError(RuntimeError):
    """Base failure for reading the current Context orientation."""


class NoCurrentContextError(CurrentContextError):
    """Raised when the active Store has no current Context pointer."""


class CurrentContextReader(Protocol):
    """Read the process-selected Store's current Context pointer."""

    def current_context_name(self) -> str | None:
        """Return the canonical public name, or ``None`` when unset."""


@dataclass(frozen=True)
class CurrentContextResult:
    """One typed orientation result shared by public adapters."""

    context_name: str


def get_current_context(reader: CurrentContextReader) -> CurrentContextResult:
    """Return current orientation without loading or authorizing a Context.

    The current pointer is deliberately weaker than READ authority.  Commands
    that consume this name must still resolve and authorize it for their own
    operation; this use case only reports the active Store's navigation state.
    """

    name = reader.current_context_name()
    if name is None:
        raise NoCurrentContextError(
            "No current Context. Run 'mem init <name>' to get started."
        )
    if not isinstance(name, str) or not name:
        raise CurrentContextError("The current Context state is invalid.")
    return CurrentContextResult(context_name=name)
