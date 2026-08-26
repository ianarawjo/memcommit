"""Pure option identity shared by terminal selection controls."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SelectionOption:
    """One stable selectable value independent of layout and operation meaning."""

    uid: str
    label: str
    description: str = ""

    def __post_init__(self) -> None:
        if (
            not isinstance(self.uid, str)
            or not self.uid
            or any(character in self.uid for character in "\r\n")
            or not isinstance(self.label, str)
            or not self.label
            or any(character in self.label for character in "\r\n")
            or not isinstance(self.description, str)
        ):
            raise ValueError("Selection options require stable text identity.")
