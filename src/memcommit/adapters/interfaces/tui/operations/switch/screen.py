"""Interactive name-selection adapter for one Switch request."""

from __future__ import annotations

from collections.abc import Callable

from memcommit.core.context_targeting.tui.picker import (
    ContextMemorySelection,
    ContextSubtreeSelection,
    choose_context,
)
from memcommit.adapters.interfaces.tui.operations.switch.model import SwitchTuiSetup
from memcommit.application.operations.switch.application import SwitchContextRequest


SwitchChooser = Callable[..., str | ContextSubtreeSelection | ContextMemorySelection | None]


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
