"""Operation-neutral values for composing terminal screen regions."""

from __future__ import annotations

from dataclasses import dataclass

from prompt_toolkit.layout.containers import AnyContainer


@dataclass(frozen=True)
class TuiRegion:
    """One vertical screen region and its presentation boundary."""

    container: AnyContainer
    separator_before: bool = False
