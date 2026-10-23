"""Read retained local evidence without traversing other Profiles."""

from __future__ import annotations

from typing import Any, Protocol

from memcommit.models.context import Context


class HistoryEvidenceSource(Protocol):
    """Raw local evidence interface used by History reconstruction. The caller supplies exact Context names; implementations own I/O."""

    def list_context_names(self) -> list[str]: ...

    def load_direct(self, name: str) -> Context: ...

    def list_checkpoints(self, context_name: str) -> list[dict[str, Any]]: ...

    def load_atomize_analysis(self, context_uid: str) -> Any: ...

    def load_update_receipt(self, operation_uid: str) -> Any: ...


__all__ = ["HistoryEvidenceSource"]
