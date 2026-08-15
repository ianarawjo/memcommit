"""Typed values owned by the Fit terminal adapter."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FitClipboardProjection:
    """One deterministic focused or complete Fit clipboard document."""

    text: str
    label: str

    def __post_init__(self) -> None:
        if not self.text or not self.label:
            raise ValueError("Fit clipboard projection must be nonblank.")
