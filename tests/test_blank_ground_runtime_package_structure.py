from importlib import import_module


def test_blank_ground_runtime_separates_four_live_responsibilities() -> None:
    runtime = import_module("memcommit.adapters.console.commands.ground.shell.runtime")
    entry = import_module(
        "memcommit.adapters.console.commands.ground.shell.runtime.entry"
    )
    session = import_module(
        "memcommit.adapters.console.commands.ground.shell.runtime.session"
    )
    drafting = import_module(
        "memcommit.adapters.console.commands.ground.shell.runtime.grounding_drafting"
    )
    contexts = import_module(
        "memcommit.adapters.console.commands.ground.shell.runtime.context_selection"
    )
    terminal = import_module(
        "memcommit.adapters.console.commands.ground.shell.runtime.terminal_interaction"
    )

    assert runtime.run_ground_shell is entry.run_ground_shell
    assert session.GroundShellState.__module__.startswith(session.__name__)
    assert drafting.GroundingDraftResponse.__module__.startswith(drafting.__name__)
    assert contexts.GroundContextCandidateRow.__module__.startswith(contexts.__name__)
    assert terminal.pane_activity_text.__module__.startswith(terminal.__name__)


def test_blank_ground_application_separates_interaction_owners() -> None:
    application = import_module(
        "memcommit.adapters.console.commands.ground.shell.runtime."
        "terminal_interaction.application"
    )
    entrypoint = import_module(f"{application.__name__}.entrypoint")
    view = import_module(f"{application.__name__}.workbench_view")
    turns = import_module(f"{application.__name__}.turn_controller")
    keybindings = import_module(f"{application.__name__}.keybindings")
    grounding = import_module(f"{application.__name__}.grounding_coordinator")

    assert application.run_ground_shell is entrypoint.run_ground_shell
    assert view.BlankGroundWorkbenchView.__module__ == view.__name__
    assert turns.BlankGroundTurnController.__module__ == turns.__name__
    assert (
        keybindings.install_blank_ground_keybindings.__module__ == keybindings.__name__
    )
    assert grounding.BlankGroundGroundingCoordinator.__module__ == grounding.__name__
