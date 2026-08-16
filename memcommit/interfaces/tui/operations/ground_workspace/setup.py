"""Save Location adapter for creating one physical Ground workspace."""

from __future__ import annotations

from collections.abc import Callable

from memcommit.context_targeting.tui.name_editor import (
    ContextNameView,
    choose_context_name,
)
from memcommit.interfaces.tui.operations.ground_workspace.model import (
    GroundWorkspaceLocationSetup,
)


def run_ground_workspace_location_tui(
    setup: GroundWorkspaceLocationSetup,
    *,
    chooser: Callable[[ContextNameView], str | None] = choose_context_name,
) -> str | None:
    """Return an exact uncreated root name without creating or switching."""

    return chooser(
        ContextNameView(
            value=setup.initial_name,
            label="NEW GROUND · SAVE LOCATION",
            state="NOT CREATED",
            detail=(
                "Enter continues to an unsaved Ground. Its root and five fixed "
                "child Contexts are created only after exact command approval."
            ),
            validate=setup.validate_name,
            context_names=setup.context_names,
            current_context=setup.current_context,
        )
    )


__all__ = ["run_ground_workspace_location_tui"]
