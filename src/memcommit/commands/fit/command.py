"""Judge proposition compatibility or inspect the explicit Ground adapter."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.commands.shared.command_progress import CommandProgress
from memcommit.context_targeting.resolution import parse_direct_memory_locator
from memcommit.application.operations.fit.ground_report import FitError, FitReport
from memcommit.application.operations.fit.application import (
    FitMemorySourceRequest,
    FitPropositionsRequest,
    FitRequest,
    FitResult,
    FitStoredSourcesRequest,
)
from memcommit.application.operations.fit.judgment import FitJudgmentError, FitProposition
from memcommit.application.operations.fit.runtime import (
    FitSourceError,
    run_fit_with_store,
    run_proposition_fit,
    run_stored_source_fit,
)
from memcommit.adapters.interfaces.cli.fit import (
    render_fit_plain,
    render_proposition_fit_plain,
)
from memcommit.adapters.interfaces.console.text import display_escape_text
from memcommit.adapters.interfaces.fit import fit_result_text
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.infrastructure.providers.subscription import QueryProviderError, connect_semantic_provider
from memcommit.persistence.store import MemoryStore


def render_fit(report: FitReport, *, current: bool = True) -> str:
    """Compatibility projection for callers of the former command renderer."""

    return fit_result_text(FitResult(report, current))


def _memory_source_operand(value: str) -> FitMemorySourceRequest:
    """Parse the CLI's optional ``CONTEXT:UID`` direct-Memory spelling."""

    text = value.strip()
    if not text:
        raise FitSourceError("A Fit Memory selector must be nonblank.")
    try:
        locator = parse_direct_memory_locator(text)
    except ValueError as error:
        raise FitSourceError(str(error)) from error
    return FitMemorySourceRequest(
        selector=locator.memory_selector,
        context_locator=locator.context_locator,
    )


def cmd(
    propositions: Annotated[
        Optional[list[str]],
        typer.Argument(
            help=(
                "Auto operand: readable Context, Memory UID/prefix, or literal "
                "proposition; use text:VALUE to force literal text; when "
                "omitted, use the current Context's direct Memories"
            )
        ),
    ] = None,
    background: Annotated[
        Optional[list[str]],
        typer.Option(
            "--background",
            help="Repeatable background proposition used as Context K",
        ),
    ] = None,
    memory_sources: Annotated[
        Optional[list[str]],
        typer.Option(
            "--memory",
            metavar="[CONTEXT:]UID_OR_PREFIX",
            help=(
                "Repeatable direct Memory source; an unqualified selector uses "
                "the command-start current Context"
            ),
        ),
    ] = None,
    context_sources: Annotated[
        Optional[list[str]],
        typer.Option(
            "--context",
            "-c",
            metavar="CONTEXT",
            help=(
                "Repeatable readable Context whose direct ordinary Memories "
                "join the proposition set"
            ),
        ),
    ] = None,
    ground_name: Annotated[
        Optional[str],
        typer.Option(
            "--ground",
            help=(
                "Check one revision-bound Ground across Context, Goal, Rules, "
                "and Examples"
            ),
        ),
    ] = None,
    receipt: Annotated[
        Optional[str],
        typer.Option(
            "--receipt",
            help="Show one immutable Fit receipt by exact uid instead of running Fit",
        ),
    ] = None,
    plain: Annotated[
        bool,
        typer.Option(
            "--plain",
            hidden=True,
            help="Print the same compact Fit receipt without terminal color",
        ),
    ] = False,
) -> None:
    """Judge whether every supplied proposition can jointly hold."""

    try:
        raw_propositions = tuple(propositions or ())
        raw_background = tuple(background or ())
        raw_memory_sources = tuple(memory_sources or ())
        raw_context_sources = tuple(context_sources or ())
        if ground_name is not None:
            if (
                raw_propositions
                or raw_background
                or raw_memory_sources
                or raw_context_sources
            ):
                raise FitError(
                    "Choose proposition operands or --ground, not both; "
                    "Memory/Context sources count as proposition operands."
                )

            def execute_ground(request: FitRequest) -> FitResult:
                store = MemoryStore(create=False)
                if request.receipt_uid is not None:
                    return run_fit_with_store(
                        request,
                        store=store,
                        provider_factory=connect_semantic_provider,
                    )
                with CommandProgress(
                    "FIT", "checking Ground", total=1
                ) as progress:
                    result = run_fit_with_store(
                        request,
                        store=store,
                        provider_factory=connect_semantic_provider,
                    )
                    progress.update("receipt saved", step=1)
                return result

            render_fit_plain(
                execute_ground(
                    FitRequest(ground_name=ground_name, receipt_uid=receipt)
                ),
                color=False if plain else None,
            )
            return

        if receipt is not None:
            raise FitError("--receipt requires the explicit --ground adapter.")
        background_propositions = tuple(
            FitProposition(f"k{index}", content, "PROPOSITION")
            for index, content in enumerate(raw_background, 1)
        )

        general_request: FitPropositionsRequest | FitStoredSourcesRequest
        if raw_propositions or raw_memory_sources or raw_context_sources:
            general_request = FitStoredSourcesRequest(
                propositions=(),
                background=background_propositions,
                auto_operands=raw_propositions,
                memory_sources=tuple(
                    _memory_source_operand(value) for value in raw_memory_sources
                ),
                context_locators=raw_context_sources,
            )
        else:
            # A bare Fit command is the Context-level convenience form. Keep
            # the default as an explicit relative locator so the stored-source
            # runtime freezes the command-start current Context exactly once.
            general_request = FitStoredSourcesRequest(
                propositions=(),
                background=background_propositions,
                context_locators=(".",),
            )

        def execute_propositions(
            next_request: FitPropositionsRequest | FitStoredSourcesRequest,
        ):
            with CommandProgress(
                "FIT", "checking propositions", total=1
            ) as progress:
                result = (
                    run_stored_source_fit(
                        next_request,
                        store=MemoryStore(create=False),
                        provider_factory=connect_semantic_provider,
                    )
                    if isinstance(next_request, FitStoredSourcesRequest)
                    else run_proposition_fit(
                        next_request,
                        provider_factory=connect_semantic_provider,
                    )
                )
                progress.update("judgment ready", step=1)
            return result

        render_proposition_fit_plain(
            execute_propositions(general_request),
            color=False if plain else None,
        )
    except (
        FitError,
        FitJudgmentError,
        FitSourceError,
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            "Fit error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
