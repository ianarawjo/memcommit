"""Top-level assembly for Resolution Session key bindings."""

from __future__ import annotations


from prompt_toolkit.key_binding import KeyBindings

from memcommit.adapters.console.terminal.components.session_help import (
    bind_session_help,
)
from memcommit.adapters.console.terminal.components.semantic_viewer import (
    SemanticViewerController,
)
from memcommit.adapters.console.terminal.core.keybindings import (
    NavigationAccelerator,
)

from memcommit.adapters.console.terminal.components.resolution.session_shell.controller import (
    ResolutionSessionController,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.controls import (
    ResolutionShellControls,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.editors import (
    ResolutionEditors,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.review_flow import (
    ResolutionReviewFlow,
)

from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.keymap.action_shortcuts import (
    bind_action_shortcuts,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.keymap.back_navigation import (
    bind_back_navigation,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.keymap.binding_state import (
    ResolutionKeyBindingState,
    ResolutionKeymapOptions,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.keymap.destination_bindings import (
    bind_destination_keys,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.keymap.focus_surfaces import (
    bind_focus_surfaces,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.keymap.input_focus import (
    bind_input_focus,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.keymap.navigation_bindings import (
    bind_navigation_keys,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.keymap.response_bindings import (
    bind_response_keys,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.keymap.surface_activation import (
    build_surface_activation,
)


def bind_resolution_keymap(
    bindings: KeyBindings,
    controller: ResolutionSessionController,
    controls: ResolutionShellControls,
    editors: ResolutionEditors,
    review_flow: ResolutionReviewFlow,
    viewer_controller: SemanticViewerController,
    navigation_accelerator: NavigationAccelerator,
    options: ResolutionKeymapOptions,
) -> None:
    """Compose every responsibility-specific key binding group."""

    state = ResolutionKeyBindingState(
        bindings=bindings,
        controller=controller,
        controls=controls,
        editors=editors,
        review_flow=review_flow,
        viewer_controller=viewer_controller,
        navigation_accelerator=navigation_accelerator,
        options=options,
    )
    bind_navigation_keys(state)
    activate_current_surface = build_surface_activation(state)
    bind_focus_surfaces(state, activate_current_surface)
    bind_input_focus(state)
    cancel_destination_edit = bind_destination_keys(state)
    bind_action_shortcuts(state)
    close_session = bind_back_navigation(state, cancel_destination_edit)
    bind_response_keys(state, close_session)
    bind_session_help(
        bindings,
        filter=~controls.writable_input_focused,
        app_input=options.app_input,
        app_output=options.app_output,
        study_surface="resolution",
    )
