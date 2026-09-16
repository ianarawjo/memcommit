"""Read the operation-owned Context catalog independently of Profile state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from memcommit.core.context import Context


class OperationContextsPort(Protocol):
    def context_names(self) -> tuple[str, ...]: ...

    def load_context(self, name: str) -> Context: ...


@dataclass(frozen=True)
class OperationContextEntry:
    name: str
    context: Context | None = None
    error: str | None = None


def list_operation_contexts(
    port: OperationContextsPort,
) -> tuple[OperationContextEntry, ...]:
    """Freeze the displayed contents once; one invalid file stays inspectable."""
    entries: list[OperationContextEntry] = []
    for name in port.context_names():
        try:
            entries.append(OperationContextEntry(name, port.load_context(name)))
        except (OSError, ValueError) as error:
            entries.append(OperationContextEntry(name, error=str(error)))
    return tuple(entries)
