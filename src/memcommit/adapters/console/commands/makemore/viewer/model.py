"""Typed values owned by the Makemore terminal adapter."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MakemoreClipboardProjection:
    text: str
    label: str

    def __post_init__(self) -> None:
        if not self.text or not self.label:
            raise ValueError("Makemore clipboard projection must be nonblank.")
