"""Typed process-local values for Meld endpoint setup."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.source_projection.presentation import SourceDisplayValue


@dataclass(frozen=True)
class MeldTuiSetup:
    """Frozen readable Source catalog and eligible local Result targets."""

    names: tuple[str, ...]
    left_name: str
    right_name: str
    eligible_target_names: frozenset[str]
    current_context: str | None = None
    annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()

    def __post_init__(self) -> None:
        if (
            len(self.names) < 2
            or len(set(self.names)) != len(self.names)
            or any(not isinstance(name, str) or not name for name in self.names)
        ):
            raise ValueError("Meld setup requires two distinct readable names.")
        if (
            self.left_name not in self.names
            or self.right_name not in self.names
            or self.left_name == self.right_name
        ):
            raise ValueError("Meld setup requires distinct available A/B defaults.")
        if not self.eligible_target_names <= set(self.names):
            raise ValueError(
                "One or more Meld Result targets are no longer available. "
                "Reopen Meld and select them again."
            )
        labels = dict(self.annotations)
        if len(labels) != len(self.annotations) or set(labels) - set(self.names):
            raise ValueError("Meld setup annotations are outside its catalog.")


@dataclass(frozen=True)
class MeldEndpointSelection:
    """One reviewed Meld shape returned without planning or durable mutation."""

    mode: str
    left_name: str
    right_name: str
    target_name: str | None = None
    create_target: bool = False
    left_descendants: bool = False
    right_descendants: bool = False
    left_memory_uid: str | None = None
    right_memory_uid: str | None = None

    def __post_init__(self) -> None:
        if self.mode not in {"symmetric", "directional"}:
            raise ValueError("Meld endpoint selection has an unknown mode.")
        if self.left_name == self.right_name:
            raise ValueError("Meld endpoint selection requires distinct A and B.")
        if self.mode == "symmetric" and self.target_name is None:
            raise ValueError("Symmetric Meld endpoint selection requires C.")
        if self.mode == "directional" and (
            self.target_name is not None or self.create_target
        ):
            raise ValueError("Directional Meld uses B as its result target.")
