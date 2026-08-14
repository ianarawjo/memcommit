"""Exact-name terminal adapter for one ordinary Context Init request."""

from __future__ import annotations

from collections.abc import Callable

from memcommit.context_init_application import ContextInitRequest
from memcommit.context_targeting.tui.name_editor import (
    ContextNameView,
    choose_context_name,
    suggest_fresh_context_name,
)
from memcommit.interfaces.tui.operations.context_init.model import (
    ContextInitTuiSetup,
)


def run_context_init_tui(
    *,
    setup: ContextInitTuiSetup,
    create_parents: bool,
    chooser: Callable[[ContextNameView], str | None] = choose_context_name,
) -> ContextInitRequest | None:
    """Edit one proposed name and return a request without creating anything."""

    suggestion = suggest_fresh_context_name("new-context", setup.context_names)
    name = chooser(
        ContextNameView(
            value=suggestion,
            label="NEW CONTEXT NAME",
            state="NOT CREATED",
            detail="Enter creates this exact Context and switches to it.",
            validate=setup.validate_name,
            context_names=setup.context_names,
            current_context=setup.expected_current,
        )
    )
    if name is None:
        return None
    return ContextInitRequest(
        name=name,
        create_parents=create_parents,
        expected_current=setup.expected_current,
    )
