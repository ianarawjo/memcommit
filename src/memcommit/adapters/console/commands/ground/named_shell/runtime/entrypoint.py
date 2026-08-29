"""Interactive runtime entry point for one existing named Ground."""

from __future__ import annotations

from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.output import Output

from memcommit.adapters.console.terminal.core.capabilities import (
    require_interactive_terminal,
)
from memcommit.application.operations.ground.model import GroundSession

from memcommit.adapters.console.commands.ground.named_shell.presentation import (
    _initial_question,
)
from memcommit.adapters.console.commands.ground.named_shell.proposal import (
    NamedGroundApplier,
    NamedGroundDirectEditPreparer,
    NamedGroundDraftPreparer,
    NamedGroundFitLookup,
    NamedGroundFitRunner,
    NamedGroundInterpreter,
    NamedGroundProposalRetargeter,
    NamedGroundReloader,
    NamedGroundShellResult,
    NamedGroundUseTogglePreparer,
)
from memcommit.adapters.console.commands.ground.named_shell.runtime.fit_coordinator import (
    NamedGroundFitCoordinator,
)
from memcommit.adapters.console.commands.ground.named_shell.runtime.keybindings import (
    install_named_ground_keybindings,
)
from memcommit.adapters.console.commands.ground.named_shell.runtime.state import (
    NamedGroundShellState,
)
from memcommit.adapters.console.commands.ground.named_shell.runtime.turn_controller import (
    NamedGroundTurnController,
)
from memcommit.adapters.console.commands.ground.named_shell.runtime.workbench_view import (
    NamedGroundWorkbenchView,
)


def run_named_ground_shell(
    session: GroundSession,
    *,
    interpret: NamedGroundInterpreter,
    apply: NamedGroundApplier,
    prepare_rule_draft: NamedGroundDraftPreparer | None = None,
    prepare_direct_edit: NamedGroundDirectEditPreparer | None = None,
    prepare_use_toggle: NamedGroundUseTogglePreparer | None = None,
    retarget_proposal: NamedGroundProposalRetargeter | None = None,
    reload_session: NamedGroundReloader | None = None,
    run_fit: NamedGroundFitRunner | None = None,
    lookup_fit: NamedGroundFitLookup | None = None,
    auto_fit: bool = False,
    initial_receipt: str = "",
    context_hints: tuple[str, ...] = (),
    new_context_hint: str | None = None,
    placement_catalog_names: tuple[str, ...] = (),
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> NamedGroundShellResult:
    """Run repeated one-command Ground turns until the person closes the TUI."""

    if require_tty:
        require_interactive_terminal(
            "Interactive Ground",
            snapshot_hint=(
                f"Use 'mem ground {session.contract_name} --snapshot' "
                "outside a terminal."
            ),
        )

    state = NamedGroundShellState.create(
        session,
        fit_receipt=lookup_fit(session) if lookup_fit is not None else None,
        placement_catalog_names=placement_catalog_names,
        context_hints=context_hints,
        initial_question=_initial_question(session),
        initial_receipt=initial_receipt,
        auto_fit_enabled=auto_fit and run_fit is not None,
    )
    view = NamedGroundWorkbenchView(
        state,
        context_hints=context_hints,
        new_context_hint=new_context_hint,
    )
    fit = NamedGroundFitCoordinator(
        state,
        run_fit=run_fit,
        lookup_fit=lookup_fit,
    )
    controller = NamedGroundTurnController(
        state,
        view,
        fit,
        interpret=interpret,
        apply=apply,
        prepare_rule_draft=prepare_rule_draft,
        prepare_direct_edit=prepare_direct_edit,
        prepare_use_toggle=prepare_use_toggle,
        retarget_proposal=retarget_proposal,
        reload_session=reload_session,
        lookup_fit=lookup_fit,
    )
    fit.attach(view, refresh_current=controller.refresh_current)

    bindings = KeyBindings()
    install_named_ground_keybindings(
        bindings,
        state=state,
        view=view,
        controller=controller,
        fit=fit,
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
        return application.run(
            pre_run=(
                lambda: fit.schedule_auto_fit(application)
                if state.auto_fit_enabled
                else None
            )
        )
    except (EOFError, KeyboardInterrupt):
        return state.result("CLOSED")
