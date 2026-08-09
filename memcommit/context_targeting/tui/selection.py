"""Checked Context selection and cardinality controls."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from prompt_toolkit.formatted_text.base import StyleAndTextTuples

from memcommit.commands.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.context_targeting.model import ContextSelectionMode


@dataclass
class ContextSelectionState:
    """Track selected names separately from the moving Context-tree cursor."""

    catalog: tuple[str, ...]
    mode: ContextSelectionMode
    _selected_order: list[str] = field(repr=False)
    minimum: int = 1

    @classmethod
    def create(
        cls,
        catalog: Sequence[str],
        *,
        selected: Sequence[str],
        mode: ContextSelectionMode = "SINGLE",
        minimum: int = 1,
    ) -> "ContextSelectionState":
        names = tuple(catalog)
        chosen = list(dict.fromkeys(selected))
        if (
            not names
            or len(set(names)) != len(names)
            or any(not isinstance(name, str) or not name for name in names)
        ):
            raise ValueError("Context selection requires a distinct catalog.")
        if mode not in {"SINGLE", "MULTIPLE"}:
            raise ValueError("Context selection mode must be SINGLE or MULTIPLE.")
        if isinstance(minimum, bool) or not 1 <= minimum <= len(names):
            raise ValueError("Context selection minimum is outside the catalog.")
        if any(name not in names for name in chosen) or len(chosen) < minimum:
            raise ValueError("Initial Context selections are outside the catalog.")
        if mode == "SINGLE" and len(chosen) != 1:
            raise ValueError("Single Context selection requires exactly one value.")
        return cls(names, mode, chosen, minimum)

    @property
    def selected_names(self) -> tuple[str, ...]:
        """Return stable catalog order for provider and receipt boundaries."""

        selected = frozenset(self._selected_order)
        return tuple(name for name in self.catalog if name in selected)

    @property
    def selected_set(self) -> frozenset[str]:
        return frozenset(self._selected_order)

    @property
    def most_recent_name(self) -> str:
        return self._selected_order[-1]

    @property
    def selected_name(self) -> str:
        """Return the sole selected name for a single-cardinality control."""

        if self.multiple:
            raise ValueError("Multiple Context selection has no single selected name.")
        return self._selected_order[0]

    @property
    def multiple(self) -> bool:
        return self.mode == "MULTIPLE"

    def set_multiple(self, enabled: bool) -> bool:
        """Change cardinality and collapse deterministically when needed."""

        next_mode: ContextSelectionMode = "MULTIPLE" if enabled else "SINGLE"
        if next_mode == self.mode:
            return False
        self.mode = next_mode
        if not enabled and len(self._selected_order) > 1:
            # Retain the last explicit choice rather than silently reverting to
            # the initial/current Context when a multi-root search is narrowed.
            self._selected_order = [self.most_recent_name]
            return True
        return False

    def choose(self, name: str) -> bool:
        """Choose or toggle one name and report whether the checked set changed."""

        if name not in self.catalog:
            raise ValueError("Selected Context is outside the frozen catalog.")
        if not self.multiple:
            changed = self._selected_order != [name]
            self._selected_order = [name]
            return changed
        if name in self._selected_order:
            if len(self._selected_order) <= self.minimum:
                raise ValueError(
                    f"Select at least {self.minimum} Context"
                    + ("s." if self.minimum != 1 else ".")
                )
            self._selected_order.remove(name)
            return True
        self._selected_order.append(name)
        return True


@dataclass
class ContextTargetModeState:
    """Cardinality choice for operations that expose one versus many roots."""

    choice: HorizontalChoiceState

    @classmethod
    def create(cls, *, multiple: bool) -> "ContextTargetModeState":
        return cls(
            HorizontalChoiceState(
                (
                    HorizontalChoiceOption("SINGLE", "SINGLE TARGET"),
                    HorizontalChoiceOption("MULTIPLE", "MULTIPLE TARGETS"),
                ),
                selected_uid="MULTIPLE" if multiple else "SINGLE",
            )
        )

    @property
    def multiple(self) -> bool:
        return self.choice.selected_uid == "MULTIPLE"

    def move(self, delta: int) -> bool:
        return self.choice.move(delta)


def render_context_target_mode(
    state: ContextTargetModeState,
    *,
    focused: bool,
    title: str = "TARGET SELECTION",
) -> StyleAndTextTuples:
    return render_horizontal_choice(state.choice, title=title, focused=focused)
