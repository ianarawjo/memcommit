"""Ground-specific focus-ring movement over prompt-toolkit controls."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from prompt_toolkit.application import Application

from memcommit.adapters.console.commands.ground_workbench.ground.shell.runtime.session.state import (
    GroundPane,
)


def cycle_focus(
    application: Application[Any],
    *,
    elements: Sequence[object],
    layers: Mapping[int, GroundPane],
    acknowledge: Callable[[GroundPane], None],
    step: int,
    default_index: int = 0,
) -> None:
    """Move through one explicit focus ring and acknowledge the destination."""

    current_index = next(
        (
            index
            for index, element in enumerate(elements)
            if application.layout.has_focus(element)
        ),
        default_index,
    )
    target = elements[(current_index + step) % len(elements)]
    application.layout.focus(target)
    acknowledge(layers[id(target)])
    application.invalidate()
