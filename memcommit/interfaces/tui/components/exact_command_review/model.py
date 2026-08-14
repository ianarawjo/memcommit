"""Frozen value reviewed before one exact local command is executed."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExactCommandReview:
    """A frozen argv and its complete user-facing mutation boundary."""

    argv: tuple[str, ...]
    effects: tuple[str, ...]

    def __post_init__(self) -> None:
        # Freeze caller-owned sequences so approval cannot drift after display.
        if isinstance(self.argv, (str, bytes)) or isinstance(
            self.effects,
            (str, bytes),
        ):
            raise ValueError("Exact command review requires argv sequences.")
        try:
            object.__setattr__(self, "argv", tuple(self.argv))
            object.__setattr__(self, "effects", tuple(self.effects))
        except TypeError as error:
            raise ValueError(
                "Exact command review requires argv sequences."
            ) from error
        if not self.argv or any(not isinstance(arg, str) for arg in self.argv):
            raise ValueError("Exact command review requires a non-empty argv.")
        if not self.effects or any(
            not isinstance(effect, str) or not effect.strip()
            for effect in self.effects
        ):
            raise ValueError(
                "Exact command review requires non-empty effect lines."
            )
