"""Typed process-local values returned by compact Branch setup."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BranchEndpointSelection:
    """One frozen local Source range and exact require-new target."""

    source_name: str
    target_name: str
    include_descendants: bool = False

    def __post_init__(self) -> None:
        if (
            not isinstance(self.source_name, str)
            or not self.source_name
            or not isinstance(self.target_name, str)
            or not self.target_name
            or type(self.include_descendants) is not bool
            or any(
                character in self.source_name + self.target_name for character in "\r\n"
            )
        ):
            raise ValueError("Branch setup requires exact one-line Context names.")


__all__ = ["BranchEndpointSelection"]
