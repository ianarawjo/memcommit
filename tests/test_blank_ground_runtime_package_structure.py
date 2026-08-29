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
