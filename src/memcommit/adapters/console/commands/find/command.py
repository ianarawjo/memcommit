"""Find relevant Memories using all Contexts in the active Profile."""

from typing import Annotated

from click import UsageError
import typer

from memcommit.adapters.console.commands.search.receipt import render_search_receipt
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.application.operations.search.errors import SearchError
from memcommit.application.operations.search.runtime import execute_profile_search
from memcommit.persistence.store import ProfileStore
from memcommit.providers.connection import connect_search_provider
from memcommit.providers.errors import QueryProviderError


def cmd(
    search_description: Annotated[
        str | None,
        typer.Argument(
            metavar="SEARCH DESCRIPTION",
            show_default=False,
            help="Describe what to find in all Contexts in the active Profile; returns up to 5 matches.",
        ),
    ] = None,
) -> None:
    if search_description is None or not search_description.strip():
        raise UsageError('Missing required input. Example: mem find "Search description".')
    try:
        with CommandProgress("FIND", "connecting provider", total=3) as progress:
            def observe(stage):
                if stage == "SEARCHING":
                    progress.update("ranking candidates", step=2)
                elif stage == "CHECKING_COVERAGE":
                    progress.update("checking namespace coverage", step=3)

            response = execute_profile_search(
                search_description,
                store=ProfileStore(),
                provider_factory=connect_search_provider,
                observer=observe,
            )
        render_search_receipt(
            response,
            target_names=response.request.target_names,
            all_readable_contexts=True,
        )
    except (
        SearchError,
        QueryProviderError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            "Find error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1) from error
