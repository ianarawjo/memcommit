"""List developer scenarios or run their complete durable evaluation."""

from typing import Annotated

import typer

from memcommit.adapters.console.commands.dev_eval.receipt import (
    render_eval_receipt,
)
from memcommit.adapters.console.terminal.core.output import echo_text, secho_text
from memcommit.application.operations.dev_eval.catalog import (
    get_scenario,
    list_scenarios,
)
from memcommit.persistence.store import MemoryStore
from memcommit.providers.connection import connect_semantic_provider


def cmd(
    scenario: Annotated[
        str | None,
        typer.Argument(help="Registered scenario to evaluate; omit to list scenarios."),
    ] = None,
) -> None:
    """List scenarios or dispatch the selected evaluation."""
    if scenario is None:
        secho_text("DEV EVAL  SCENARIOS", bold=True)
        for item in list_scenarios():
            echo_text("  {name}", name=item.name)
        echo_text("\nRun: mem dev-eval SCENARIO")
        return
    try:
        # Reject unknown names before opening a Store.
        selected = get_scenario(scenario)
    except ValueError as error:
        echo_text("{error}", error=error, err=True)
        raise typer.Exit(2) from error
    try:
        store = MemoryStore()
        secho_text("DEV EVAL  {name}\n", name=selected.name, bold=True)
        checks = selected.run(
            store=store,
            provider_factory=connect_semantic_provider,
        )
        render_eval_receipt(checks, current_context_name=store.current_context_name())
        if not all(passed for _, passed in checks):
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as error:
        echo_text("Dev eval error: {error}", error=error, err=True)
        raise typer.Exit(1) from error
