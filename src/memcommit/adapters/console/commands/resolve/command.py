"""Collect decisions for a complete Audit and apply one whole-Context Update."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.adapters.console import is_interactive_terminal
from memcommit.adapters.console.clipboard import write_system_clipboard
from memcommit.adapters.console.commands.resolve.workbench import (
    run_resolve_tui,
)
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
)
from memcommit.adapters.console.commands.resolve.analysis import render_resolve_plain
from memcommit.adapters.console.commands.resolve.receipt import render_resolve_receipt
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.application.capabilities.operand_resolution import (
    freeze_local_context_operand_candidates,
    resolve_existing_context_operand,
)
from memcommit.providers.subscription import (
    QueryProviderError,
    connect_semantic_provider,
)
from memcommit.application.operations.resolve.application import (
    ResolveError,
    ResolveRequest,
    run_resolve,
)
from memcommit.application.operations.resolve.decisions import (
    apply_resolve_update,
    plan_resolve_update,
)
from memcommit.application.operations.resolve.runtime import MemoryStoreResolvePort
from memcommit.application.operations.resolve.semantic import (
    ProviderResolveSemanticPort,
    all_audit_issue_keys,
)
from memcommit.application.operations.resolve.targeting import (
    normalize_resolve_cli_targets,
)
from memcommit.application.capabilities.memory_issue_analysis.handoff import (
    QualityFindingHandoffError,
    quality_finding_handoff_from_json,
)
from memcommit.application.operations.resolve.finding_handoff import (
    conflict_handoff_to_resolve_request,
)
from memcommit.persistence.store import MemoryStore
from memcommit.persistence.operations.audit import JsonAuditRecordRepository


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
            metavar="[CONTEXT:]UID_OR_PREFIX",
            help=(
                "Repeatable direct Memory restriction; short prefixes are "
                "accepted because --memory makes their role explicit"
            ),
        ),
    ] = None,
    against: Annotated[
        Optional[str],
        typer.Option(
            "--against",
            "--rule",
            metavar="RULES_CONTEXT",
            help="Optional local Rules Context for the fourth Audit section",
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
    finding_handoff: Annotated[
        Optional[str],
        typer.Option(
            "--finding-handoff",
            help="Canonical conflict handoff JSON emitted by find-conflicts",
        ),
    ] = None,
) -> None:
    """Resolve a complete Audit from finalized intent through one Update plan."""

    try:
        store = MemoryStore(create=False)
        snapshot = ContextOperandSnapshot.capture(store)
        rules_ctx = None
        if against is not None:
            rules_name = resolve_existing_context_operand(
                freeze_local_context_operand_candidates(store),
                against,
                current=snapshot.current_name,
            ).name
            rules_ctx = store.load_direct(rules_name)
        if finding_handoff is not None:
            if context_name is not None or auto_operands or memory_operands:
                raise ResolveError(
                    "Resolve --finding-handoff cannot be combined with a Context "
                    "or Memory selector."
                )
            request = conflict_handoff_to_resolve_request(
                quality_finding_handoff_from_json(finding_handoff),
                allow_create=allow_create,
                allow_delete=allow_delete,
                guidance=guidance or "",
            )
        else:
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
        port = MemoryStoreResolvePort(
            store,
            current_name=snapshot.current_name,
        )
        with CommandProgress(
            "RESOLVE",
            "building and checking repair",
            total=1,
        ) as progress:
            analysis = run_resolve(
                request,
                frame_port=port,
                semantic_port=ProviderResolveSemanticPort(),
                audit_repository=JsonAuditRecordRepository(store),
                audit_provider_factory=connect_semantic_provider,
                direction_provider_factory=connect_semantic_provider,
                conformance_rules=rules_ctx,
            )
            progress.update("Audit directions ready", step=1)

        if not analysis.review_issues or not is_interactive_terminal():
            render_resolve_plain(analysis)
            if analysis.review_issues:
                typer.echo("DECISIONS REQUIRED · reopen Resolve in an interactive terminal.")
            return

        decisions = run_resolve_tui(
            analysis,
            clipboard_writer=write_system_clipboard,
        )
        if decisions is None:
            return
        with CommandProgress(
            "RESOLVE",
            "building whole-Context Update plan",
            total=2,
        ) as progress:
            def connect_update():
                progress.update("planning exact memory changes", step=1)
                return connect_semantic_provider()

            def connect_verifier():
                progress.update("checking complete post-image", step=2)
                return connect_semantic_provider()

            proposal = plan_resolve_update(
                analysis,
                decisions,
                frame_port=port,
                update_provider_factory=connect_update,
                audit_provider_factory=connect_verifier,
            )
        if proposal.blocking_audit_keys:
            raise ResolveError(
                "The Update post-image contains "
                f"{len(proposal.blocking_audit_keys)} unforced Audit issue(s); "
                "nothing was applied. Reopen Resolve with the new evidence."
            )
        receipt = apply_resolve_update(proposal, frame_port=port)
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
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        QualityFindingHandoffError,
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


__all__ = ["cmd"]
