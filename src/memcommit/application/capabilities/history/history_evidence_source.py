"""Read-only port for evidence consumed by canonical History projections."""

from __future__ import annotations

from typing import Any, Protocol

from memcommit.core.context import Context


class HistoryEvidenceSource(Protocol):
    """Minimum raw-evidence interface required by History reconstruction.

    Implementations own I/O and authorization. History receives already
    authorized direct Context names and never uses this port to open referenced
    or query-only targets implicitly.
    """

    def list_context_names(self) -> list[str]: ...

    def load_direct(self, name: str) -> Context: ...

    def list_checkpoints(self, context_name: str) -> list[dict[str, Any]]: ...

    def load_atomize_analysis(self, context_uid: str) -> Any: ...


__all__ = ["HistoryEvidenceSource"]
