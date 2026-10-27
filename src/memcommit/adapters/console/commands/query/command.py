"""Answer one question using the active Profile's Contexts."""

from typing import Annotated

from click import UsageError
import typer

from memcommit.adapters.console.commands.query.presentation import (
    render_ordinary_query_response,
)
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.application.operations.query.ordinary_runtime import execute_profile_query
from memcommit.persistence.store import ProfileStore
from memcommit.providers.connection import connect_ordinary_query_provider


def cmd(
    question: Annotated[
        str | None,
        typer.Argument(
            metavar="QUESTION",
            show_default=False,
            help="Question to answer using all Contexts in the active Profile.",
        ),
    ] = None,
) -> None:
    if question is None or not question.strip():
        raise UsageError('Missing required input. Example: mem query "Question".')
    try:
        with CommandProgress("QUERY", "connecting provider", total=2) as progress:
            response = execute_profile_query(
                question,
                store=ProfileStore(),
                provider_factory=connect_ordinary_query_provider,
                observer=lambda stage: (
                    progress.update("answering question", step=2)
                    if stage == "ANSWERING"
                    else None
                ),
            )
        render_ordinary_query_response(response)
    except (
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            f"Query error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1) from error
