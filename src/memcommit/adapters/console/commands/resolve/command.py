"""Review conflicts and apply the changes chosen for one Context."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.adapters.console.terminal.core.capabilities import (
    require_interactive_terminal,
)
from memcommit.adapters.console.commands.resolve.receipt import (
    render_resolve_receipt,
    render_resolve_status,
)
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
)
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.application.operations.resolve.application import (
    RESOLVE_CHECKS,
    run_resolve,
)
from memcommit.application.operations.resolve.model import ResolveError, ResolveRequest
from memcommit.application.operations.resolve.issue_review import ResolveReviewInput
from memcommit.application.operations.resolve.proposal import (
    apply_resolve_proposal,
)
from memcommit.application.operations.resolve.runtime import MemoryStoreResolvePort
from memcommit.application.operations.resolve.issues import all_audit_issue_keys
from memcommit.application.operations.resolve.resolution_options.generation import (
    ProviderResolveOptionsPort,
)
from memcommit.application.operations.resolve.targeting import (
    normalize_resolve_cli_targets,
)
from memcommit.persistence.operations.audit import JsonAuditRecordRepository
from memcommit.persistence.store import MemoryStore
from memcommit.providers.connection import connect_semantic_provider
from memcommit.providers.errors import QueryProviderError


def cmd(
    auto_operands: Annotated[
        Optional[list[str]],
        typer.Argument(
            help=(
                "Auto operand: existing Context locator, Memory UID prefix, "
                "or CONTEXT:UID; omit to use the current Context"
            )
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Exact local Context or readable granted Context to repair",
        ),
    ] = None,
    memory_operands: Annotated[
        Optional[list[str]],
        typer.Option(
            "--memory",
            "-m",
            metavar="[CONTEXT:]UID_OR_PREFIX",
            help=(
                "Repeatable direct Memory restriction; short prefixes are "
                "accepted because --memory makes their role explicit"
            ),
        ),
    ] = None,
    allow_create: Annotated[
        bool,
        typer.Option(
            "--allow-create/--no-create",
            help=(
                "Allow finalized Resolve input to add supported direct Memories; "
                "enabled by default"
            ),
        ),
    ] = True,
    allow_delete: Annotated[
        bool,
        typer.Option(
            "--allow-delete",
            help="Permit a supported removal in the finalized UpdatePlan",
        ),
    ] = False,
    guidance: Annotated[
        Optional[str],
        typer.Option(
            "--guidance",
            help="Additional context available while deriving Audit directions",
        ),
    ] = None,
) -> None:
    """Review conflicts, choose resolutions, and apply the resulting changes."""

    try:
        require_interactive_terminal("Resolve")
        store = MemoryStore(create=False)
        snapshot = ContextOperandSnapshot.capture(store)
        targets = normalize_resolve_cli_targets(
            store,
            tuple(auto_operands or ()),
            context_locator=context_name,
            memory_operands=tuple(memory_operands or ()),
            current_context_name=snapshot.current_name,
        )
        request = ResolveRequest(
            context_name=targets.context_name,
            memory_selectors=targets.memory_selectors,
            allow_create=allow_create,
            allow_delete=allow_delete,
            guidance=guidance or "",
        )
        run_resolve_request(request, store=store, current_name=snapshot.current_name)
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        ResolveError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        typer.secho(
            "Resolve error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)


def run_resolve_request(
    request: ResolveRequest,
    *,
    store: MemoryStore,
    current_name: str | None,
) -> None:
    """Run review and Apply for the parsed Resolve request."""
    port = MemoryStoreResolvePort(
        store,
        current_name=current_name,
    )
    with CommandProgress(
        "RESOLVE",
        "building and checking repair",
        total=1,
    ) as progress:
        analysis = run_resolve(
            request,
            checks=RESOLVE_CHECKS,
            frame_port=port,
            semantic_port=ProviderResolveOptionsPort(),
            audit_repository=JsonAuditRecordRepository(store),
            audit_provider_factory=connect_semantic_provider,
            direction_provider_factory=connect_semantic_provider,
        )
        progress.update("Audit directions ready", step=1)

    if not analysis.issues:
        render_resolve_status(analysis)
        return

    from memcommit.adapters.console.commands.resolve.resolution_rounds import (
        run_resolution_rounds,
    )

    proposal = run_resolution_rounds(
        (ResolveReviewInput(analysis),),
        frame_port=port,
        provider_factory=connect_semantic_provider,
    )
    if proposal is None:
        return
    (proposal,) = proposal
    receipt = apply_resolve_proposal(proposal, frame_port=port)
    render_resolve_receipt(
        receipt,
        verification=(
            f"AUDIT ISSUES {len(all_audit_issue_keys(proposal.post_audit))}"
            + (
                f" · {len(receipt.unresolved_issue_uids)} FORCED"
                if receipt.unresolved_issue_uids
                else ""
            )
        ),
    )


__all__ = ["cmd", "run_resolve_request"]
