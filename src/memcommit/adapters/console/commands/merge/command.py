"""One CLI grammar and Setup for exact Context-to-Context Merge."""

from typing import Annotated, Optional

import typer

from memcommit.adapters.console.commands.merge.endpoint_setup import (
    choose_merge_request,
)
from memcommit.adapters.console.commands.merge.preview import (
    run_merge_preview,
)
from memcommit.adapters.console.commands.resolve.resolution_rounds import run_resolution_rounds
from memcommit.adapters.console.coordination.endpoint_operand import (
    choose_endpoint_operand,
)
from memcommit.adapters.console.terminal.components.command_wait import run_command_wait
from memcommit.adapters.console.terminal.core.capabilities import (
    require_interactive_terminal,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.provider_contract import (
    MemoryRelationProviderError,
)
from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
)
from memcommit.application.operations.merge.apply import apply_merge
from memcommit.application.operations.merge.inputs import (
    MergeDecision,
    MergeRequest,
    PreparedMerge,
)
from memcommit.application.operations.merge.preparation import (
    prepare_literal_merge,
    prepare_merge,
)
from memcommit.application.operations.merge.resolve_preparation import (
    prepare_semantic_review,
)
from memcommit.application.operations.merge.result import finish_merge
from memcommit.application.operations.merge.setup import (
    build_merge_setup,
    merge_target_permission,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.operations.audit import JsonAuditRecordRepository
from memcommit.persistence.store import MemoryStore
from memcommit.providers.connection import connect_semantic_provider
from memcommit.providers.errors import QueryProviderError

from .conflict_screen import run_merge_conflicts


def cmd(
    source: Annotated[
        Optional[str],
        typer.Argument(help="Existing Source Context; omit to open Setup."),
    ] = None,
    target: Annotated[
        Optional[str],
        typer.Argument(
            help="Existing Target Context; defaults to the current Context."
        ),
    ] = None,
    from_: Annotated[
        Optional[str], typer.Option("--from", help="Source Context.")
    ] = None,
    into: Annotated[
        Optional[str], typer.Option("--into", help="Target Context.")
    ] = None,
    to: Annotated[Optional[str], typer.Option("--to", help="Target Context.")] = None,
    literal: Annotated[
        bool,
        typer.Option(
            "--literal", help="Merge stored items without semantic inference."
        ),
    ] = False,
    keep_target_all: Annotated[
        bool,
        typer.Option(
            "--keep-target-all", help="With --literal: keep Target for every conflict."
        ),
    ] = False,
    take_source_all: Annotated[
        bool,
        typer.Option(
            "--take-source-all", help="With --literal: take Source for every conflict."
        ),
    ] = False,
    keep_both_all: Annotated[
        bool,
        typer.Option(
            "--keep-both-all",
            help="With --literal: retain both versions of every Memory conflict.",
        ),
    ] = False,
) -> None:
    """Merge two exact Contexts; review Setup changes before Apply."""
    try:
        source = choose_endpoint_operand(
            source, role="Source", options=(("--from", from_),)
        )
        target = choose_endpoint_operand(
            target, role="Target", options=(("--into", into), ("--to", to))
        )
        if sum((keep_target_all, take_source_all, keep_both_all)) > 1:
            raise ValueError(
                "Choose one of --keep-target-all, --take-source-all, or --keep-both-all."
            )
        if not literal and any((keep_target_all, take_source_all, keep_both_all)):
            raise ValueError(
                "--keep-target-all, --take-source-all, and --keep-both-all require --literal."
            )
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error

    try:
        # Reject an unavailable console before Store access or semantic work.
        require_interactive_terminal("Merge")
        store = MemoryStore(create=False)
        current_name = store.current_context_name()
        method = "LITERAL" if literal else "SEMANTIC"
        from_setup = source is None
        bulk = (
            MergeDecision.KEEP_TARGET
            if keep_target_all
            else MergeDecision.TAKE_SOURCE
            if take_source_all
            else MergeDecision.KEEP_BOTH
            if keep_both_all
            else None
        )
        if from_setup:
            setup = build_merge_setup(
                store, current_name=current_name, method=method, requested_target=target
            )
            request = choose_merge_request(setup, literal_only=bulk is not None)
            if request is None:
                typer.echo("Merge cancelled; no changes made.")
                return
        else:
            # Both locators use the same command-start snapshot. UID selectors
            # resolve to canonical names here as well, before planning/approval.
            source_access = resolve_existing_context_access(
                store, source, current_name=current_name
            ).value
            target_access = resolve_existing_context_access(
                store,
                target,
                current_name=current_name,
                required_permission=merge_target_permission(method),
            ).value
            request = MergeRequest(
                source_access.access_name, target_access.access_name, method
            )

        result = execute_merge(
            request,
            store=store,
            current_name=current_name,
            bulk=bulk,
            review_before_apply=from_setup,
        )
        if result is None:
            typer.echo("Merge cancelled; no changes made.")
        else:
            from memcommit.adapters.console.commands.merge.receipt import (
                render_merge_receipt,
            )

            typer.echo(render_merge_receipt(result))
    except (
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        MemoryRelationProviderError,
    ) as error:
        typer.secho(
            f"Merge error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1) from error


def execute_merge(
    request: MergeRequest,
    *,
    store,
    current_name,
    bulk=None,
    review_before_apply=False,
):
    """Prepare once, then enter the same review/publication flow for either method."""
    prepared = prepare_merge(request, store=store, current_name=current_name)
    review = prepare_literal_merge(prepared.literal_input)
    return review_merge(
        prepared,
        review,
        provider_factory=connect_semantic_provider,
        repository=JsonAuditRecordRepository(store),
        bulk=bulk,
        review_before_apply=review_before_apply,
    )


def review_merge(
    prepared: PreparedMerge,
    review,
    *,
    provider_factory,
    repository=None,
    bulk=None,
    review_before_apply=False,
):
    """Resolve → Preview → Apply through the same flow for either method."""
    literal = run_merge_conflicts(review, bulk=bulk)
    if literal is None:
        return None
    resolved = None
    if prepared.request.method == "SEMANTIC":
        semantic_review = run_command_wait(
            "MERGE",
            "auditing the merged Context",
            total=1,
            work=lambda progress: prepare_semantic_review(
                prepared,
                literal,
                provider_factory=provider_factory,
                repository=repository,
            ),
        )
        results = run_resolution_rounds(
            (semantic_review,),
            provider_factory=provider_factory,
            preview_choices=True,
            header_label="MERGE · RESOLVE",
        )
        if results is None:
            return None
        (resolved,) = results
    result = finish_merge(prepared, literal, resolved)

    def apply_reviewed(reviewed):
        return apply_merge(prepared, reviewed)

    interactive_decisions = bulk is None and any(
        round.decisions.decisions for round in result.rounds
    )
    if review_before_apply or interactive_decisions:
        return run_merge_preview(prepared, result, apply_preview=apply_reviewed)
    return apply_reviewed(result)
