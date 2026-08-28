"""Typed process-local receipt returned by Branch setup."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BranchCreationReceipt:
    """One frozen Source range and exact require-new branch target."""

    source_name: str
    target_name: str
    include_descendants: bool = False

    @property
    def new_name(self) -> str:
        """Compatibility spelling for callers that only accepted new targets."""

        return self.target_name


__all__ = ["BranchCreationReceipt"]
