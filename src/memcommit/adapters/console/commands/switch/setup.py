"""Interactive name-selection adapter for one Switch request."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Mapping

from memcommit.application.operations.switch.application import SwitchContextRequest
from memcommit.core.context_targeting.tui.picker import (
    ContextMemoryRow,
    ContextMemorySelection,
    ContextSubtreeSelection,
    choose_context,
)
from memcommit.source_projection.presentation import SourceDisplayValue


@dataclass(frozen=True)
class SwitchTuiSetup:
    """One frozen picker namespace and its lazy read-only preview adapter."""

    expected_current: str | None
    local_context_names: tuple[str, ...]
    virtual_context_names: tuple[str, ...] = ()
    selectable_virtual_names: frozenset[str] = frozenset()
    local_annotations: Mapping[str, SourceDisplayValue] = field(default_factory=dict)
    virtual_annotations: Mapping[str, SourceDisplayValue] = field(default_factory=dict)
    memory_loader: Callable[[str], Sequence[ContextMemoryRow]] | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        all_names = self.local_context_names + self.virtual_context_names
        if len(set(all_names)) != len(all_names) or any(
            not isinstance(name, str) or not name for name in all_names
        ):
            raise ValueError("Switch TUI requires a distinct Context catalog.")
        if self.expected_current is not None and (
            not isinstance(self.expected_current, str) or not self.expected_current
        ):
            raise ValueError("Switch TUI current Context is invalid.")
        if not self.selectable_virtual_names.issubset(self.virtual_context_names):
            raise ValueError("Switch TUI selectable virtual Context is unknown.")
        if self.memory_loader is not None and not callable(self.memory_loader):
            raise TypeError("Switch TUI Memory loader is invalid.")


SwitchChooser = Callable[
    ..., str | ContextSubtreeSelection | ContextMemorySelection | None
]


def run_switch_tui(
    setup: SwitchTuiSetup,
    *,
    chooser: SwitchChooser = choose_context,
) -> SwitchContextRequest | None:
    """Return a typed request without loading, validating, or switching state."""

    options: dict[str, object] = {
        "current": setup.expected_current,
        "accept_label": "switch",
        "memory_loader": setup.memory_loader,
    }
    if setup.local_annotations:
        options["local_annotations"] = setup.local_annotations
    if setup.virtual_context_names:
        options.update(
            {
                "virtual_names": setup.virtual_context_names,
                "selectable_virtual_names": setup.selectable_virtual_names,
                "virtual_annotations": setup.virtual_annotations,
            }
        )
    selected = chooser(list(setup.local_context_names), **options)
    if selected is None:
        return None
    if not isinstance(selected, str):
        raise ValueError("Switch picker returned a non-Context selection.")
    return SwitchContextRequest(
        selector=selected,
        expected_current=setup.expected_current,
    )


__all__ = ["SwitchTuiSetup", "run_switch_tui"]
