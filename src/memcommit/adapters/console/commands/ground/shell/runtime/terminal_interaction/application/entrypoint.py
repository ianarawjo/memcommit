"""Interactive runtime entry point for one blank Ground draft."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from importlib import import_module

from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.output import Output

from memcommit.adapters.console.commands.ground.shell.proposal import (
    GroundApplier,
    GroundInterpreter,
    GroundShellProposal,
    GroundShellResult,
)
from memcommit.adapters.console.commands.ground.shell.runtime.session import (
    GroundShellState,
    prepare_ground_shell_start,
)
from memcommit.adapters.console.commands.ground.shell.runtime.terminal_interaction.application.grounding_coordinator import (
    BlankGroundGroundingCoordinator,
)
from memcommit.adapters.console.commands.ground.shell.runtime.terminal_interaction.application.keybindings import (
    install_blank_ground_keybindings,
)
from memcommit.adapters.console.commands.ground.shell.runtime.terminal_interaction.application.turn_controller import (
    BlankGroundTurnController,
)
from memcommit.adapters.console.commands.ground.shell.runtime.terminal_interaction.application.workbench_view import (
    GROUND_CONTEXTS_FRAME_HEIGHT,
    GROUND_GOAL_FRAME_HEIGHT,
    GROUND_LOCATION_FRAME_HEIGHT,
    INITIAL_QUESTION,
    BlankGroundWorkbenchView,
)
from memcommit.adapters.console.terminal.components.progress import (
    BUSY_FRAMES,
    BUSY_INTERVAL_SECONDS,
)
from memcommit.adapters.console.terminal.core.capabilities import (
    require_interactive_terminal,
)
from memcommit.core.context_targeting.naming import validate_portable_context_name


_THINKING_SUFFIXES = BUSY_FRAMES
_THINKING_INTERVAL_SECONDS = BUSY_INTERVAL_SECONDS

__all__ = [
    "GROUND_CONTEXTS_FRAME_HEIGHT",
    "GROUND_GOAL_FRAME_HEIGHT",
    "GROUND_LOCATION_FRAME_HEIGHT",
    "INITIAL_QUESTION",
    "_THINKING_INTERVAL_SECONDS",
    "run_ground_shell",
]


def run_ground_shell(
    *,
    interpret: GroundInterpreter,
    apply: GroundApplier,
    ground_name: str | None = None,
    initial_request: str = "",
    initial_proposal: GroundShellProposal | None = None,
    initial_submitted_turns: Sequence[str] = (),
    current_context_name: str | None = None,
    context_catalog_count: int = 0,
    context_catalog_names: Sequence[str] = (),
    validate_new_context: Callable[[str], str] = validate_portable_context_name,
    choose_save_location: Callable[[str | None], str | None] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    background_interpretation: bool = True,
) -> GroundShellResult:
    """Run the blank-Ground dialogue until one command is applied or cancelled."""

    if require_tty:
        require_interactive_terminal(
            "Interactive Ground",
            snapshot_hint=("Run 'mem ground' in a terminal or use a snapshot mode."),
        )

    start = prepare_ground_shell_start(
        ground_name=ground_name,
        initial_request=initial_request,
        initial_proposal=initial_proposal,
        initial_submitted_turns=initial_submitted_turns,
        context_catalog_count=context_catalog_count,
        context_catalog_names=context_catalog_names,
    )
    state = GroundShellState.create(
        fixed_ground_name=start.fixed_ground_name,
        initial_proposal=start.frozen_initial_proposal,
        initial_turns=start.frozen_initial_turns,
        working_goal=start.working_goal,
        context_catalog_count=context_catalog_count,
        initial_question=INITIAL_QUESTION,
    )
    runtime_api = import_module(
        "memcommit.adapters.console.commands.ground.shell.runtime"
    )
    thinking_interval_seconds = getattr(
        runtime_api,
        "_THINKING_INTERVAL_SECONDS",
        _THINKING_INTERVAL_SECONDS,
    )
    view = BlankGroundWorkbenchView(
        state,
        fixed_ground_name=start.fixed_ground_name,
        frozen_initial_proposal=start.frozen_initial_proposal,
        working_goal=start.working_goal,
        current_context_name=current_context_name,
        context_catalog_count=context_catalog_count,
        context_catalog_names=tuple(context_catalog_names),
        thinking_suffixes=_THINKING_SUFFIXES,
    )
    grounding = BlankGroundGroundingCoordinator(
        state,
        view,
        interpret=interpret,
        fixed_ground_name=start.fixed_ground_name,
        context_catalog_count=context_catalog_count,
        background_interpretation=background_interpretation,
        thinking_interval_seconds=thinking_interval_seconds,
    )
    controller = BlankGroundTurnController(
        state,
        view,
        grounding,
        apply=apply,
        validate_new_context=validate_new_context,
    )
    bindings = KeyBindings()
    install_blank_ground_keybindings(
        bindings,
        state=state,
        view=view,
        controller=controller,
        choose_save_location=choose_save_location,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    application = view.build_application(
        bindings,
        app_input=app_input,
        app_output=app_output,
    )

    try:
        if initial_request.strip():
            state.submitted_turns.append(start.working_goal)
            if background_interpretation:
                return application.run(
                    pre_run=lambda: controller.start_initial_turn(start.working_goal)
                )
            controller.start_initial_turn(start.working_goal)
        return application.run()
    except (EOFError, KeyboardInterrupt):
        return state.result("CANCELLED")
    finally:
        state.shell_closed = True
