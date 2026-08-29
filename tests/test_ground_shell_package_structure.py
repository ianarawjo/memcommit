from importlib import import_module


def test_blank_ground_shell_facade_preserves_the_public_import_path() -> None:
    facade = import_module("memcommit.adapters.console.commands.ground.shell")
    presentation = import_module(
        "memcommit.adapters.console.commands.ground.shell.presentation"
    )
    proposal = import_module(
        "memcommit.adapters.console.commands.ground.shell.proposal"
    )
    runtime = import_module("memcommit.adapters.console.commands.ground.shell.runtime")

    assert facade.GroundShellProposal is proposal.GroundShellProposal
    assert facade.render_ground_top_panel is presentation.render_ground_top_panel
    assert facade.run_ground_shell is runtime.run_ground_shell


def test_named_ground_shell_facade_preserves_the_public_import_path() -> None:
    facade = import_module("memcommit.adapters.console.commands.ground.named_shell")
    presentation = import_module(
        "memcommit.adapters.console.commands.ground.named_shell.presentation"
    )
    proposal = import_module(
        "memcommit.adapters.console.commands.ground.named_shell.proposal"
    )
    runtime = import_module(
        "memcommit.adapters.console.commands.ground.named_shell.runtime"
    )

    assert facade.GroundCommandProposal is proposal.GroundCommandProposal
    assert (
        facade.render_named_ground_top_panel
        is presentation.render_named_ground_top_panel
    )
    assert facade.run_named_ground_shell is runtime.run_named_ground_shell


def test_named_ground_runtime_separates_live_responsibility_owners() -> None:
    runtime = import_module(
        "memcommit.adapters.console.commands.ground.named_shell.runtime"
    )
    entrypoint = import_module(
        "memcommit.adapters.console.commands.ground.named_shell.runtime.entrypoint"
    )
    state = import_module(
        "memcommit.adapters.console.commands.ground.named_shell.runtime.state"
    )
    view = import_module(
        "memcommit.adapters.console.commands.ground.named_shell.runtime.workbench_view"
    )
    turns = import_module(
        "memcommit.adapters.console.commands.ground.named_shell.runtime.turn_controller"
    )
    keybindings = import_module(
        "memcommit.adapters.console.commands.ground.named_shell.runtime.keybindings"
    )
    fit = import_module(
        "memcommit.adapters.console.commands.ground.named_shell.runtime.fit_coordinator"
    )

    assert runtime.run_named_ground_shell is entrypoint.run_named_ground_shell
    assert state.NamedGroundShellState.__module__ == state.__name__
    assert view.NamedGroundWorkbenchView.__module__ == view.__name__
    assert turns.NamedGroundTurnController.__module__ == turns.__name__
    assert (
        keybindings.install_named_ground_keybindings.__module__ == keybindings.__name__
    )
    assert fit.NamedGroundFitCoordinator.__module__ == fit.__name__
