"""Shared dependencies and policy for Resolution Session key bindings."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.output import Output

from memcommit.adapters.console.terminal.components.semantic_viewer import (
    SemanticViewerController,
)
from memcommit.adapters.console.terminal.core.keybindings import NavigationAccelerator

from memcommit.adapters.console.terminal.components.resolution.session_shell.controller import (
    ResolutionSessionController,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.presentation import (
    ResolutionDestination,
    ResolutionGlobalStrategy,
    SessionTodoView,
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


@dataclass(frozen=True)
class ResolutionKeymapOptions:
    """Operation policy and callbacks that change available key behavior."""

    split_viewer_items: bool
    global_strategies: tuple[ResolutionGlobalStrategy, ...]
    review_and_apply: bool
    read_only: bool
    read_only_handoff: SessionTodoView | None
    destination: ResolutionDestination | None
    destination_available: bool
    draft_saver: Callable[[str, str | None, str], None] | None
    response_validator: Callable[[str], None] | None
    save_draft_on_close: bool
    toggle_sort: Callable[[], None] | None
    app_input: Input | None
    app_output: Output | None


@dataclass(frozen=True)
class ResolutionKeyBindingState:
    """Live owners targeted by every Resolution Session key binding group."""

    bindings: KeyBindings
    controller: ResolutionSessionController
    controls: ResolutionShellControls
    editors: ResolutionEditors
    review_flow: ResolutionReviewFlow
    viewer_controller: SemanticViewerController
    navigation_accelerator: NavigationAccelerator
    options: ResolutionKeymapOptions
