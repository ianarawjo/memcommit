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
