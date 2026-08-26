"""Typed values owned by the Elaborate terminal adapter."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ElaborateClipboardProjection:
    text: str
    label: str

    def __post_init__(self) -> None:
        if not self.text or not self.label:
            raise ValueError("Elaborate clipboard projection must be nonblank.")
