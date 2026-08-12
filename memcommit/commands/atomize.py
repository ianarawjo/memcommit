"""Inspect or explicitly apply the latest saved atomize analysis."""

from __future__ import annotations

import sys
from dataclasses import replace
from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.atomize import (
    AtomizeAnalysisSession,
    AtomizeImpactError,
    apply_atomize_analysis,
    atomize_analysis_matches_context,
)
from memcommit.atomize_workbench import (
    AtomizeWorkbenchError,
    atomize_workbench_declared_frames,
    atomize_workbench_response_digest,
    create_atomize_workbench,
    project_atomize_workbench_findings,
)
from memcommit.atomize_workflow import open_or_create_atomize_workbench
from memcommit.commands.atomize_workbench_shell import (
    render_atomize_workbench_snapshot,
    run_atomize_workbench_shell,
)
from memcommit.commands.atomize_grounding import (
    AtomizeGroundingCommandError,
    accept_grounding,
    assert_current_grounding_bindings,
    keep_grounding_review_only,
    render_grounding_session,
    reply_to_grounding,
    start_grounding,
)
from memcommit.commands.command_progress import progressing_provider_factory
from memcommit.commands.atomize_sessions import (
    atomize_analysis_was_applied,
    atomize_planned_output_was_applied,
    atomize_workbench_was_applied,
    choose_atomize_session,
    load_saved_atomize_analysis,
    revalidate_saved_atomize_analysis,
)
from memcommit.commands.endpoint_setup_flows import choose_atomize_setup
from memcommit.commands.session_picker import SessionNewReceipt
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.commands.review_shell import ReviewCancelled
from memcommit.context import AutoCheckpoint, Memory, MemoryRef
from memcommit.review import (
    atomize_review_declared_frames,
    atomize_review_matches_analysis,
    direct_context_digest,
    review_response_digest,
)
from memcommit.store import MemoryStore, context_record_digest
from memcommit.study_prewarm.atomize import (
    find_declared_atomize_prewarm,
    is_installed_atomize_prewarm,
)
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.resolution_workbench import ResolutionWorkbenchAction


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


_UNRESOLVED_AT_APPLY_KINDS = {
    "AMBIGUITY",
    "CONFLICT",
    "ATOMIZE_UNCERTAINTY",
}


def _incorporable_workbench_response_count(
    analysis: AtomizeAnalysisSession,
    workbench,
) -> int:
    """Count answered unary findings that can revise Atomize output."""

    if workbench is None:
        return 0
    findings = {
        finding.uid: finding for finding in project_atomize_workbench_findings(analysis)
    }
    return sum(
        response.answered and len(findings[issue_uid].source_uids) == 1
        for issue_uid, response in workbench.responses.items()
    )


def _atomize_application_audit(
    analysis: AtomizeAnalysisSession,
    workbench,
) -> dict[str, object]:
    """Freeze unresolved-at-apply state without treating silence as a choice."""

    responses = {} if workbench is None else workbench.responses
    unresolved = []
    for finding in project_atomize_workbench_findings(analysis):
        if finding.kind not in _UNRESOLVED_AT_APPLY_KINDS:
            continue
        response = responses.get(finding.uid)
        unresolved.append(
            {
                "issue_uid": finding.uid,
                "kind": finding.kind,
                "source_uids": list(finding.source_uids),
                "classification": finding.classification,
                "reason": finding.reason,
                "response_state": (
                    "ANSWERED_RETAINED"
                    if response is not None and response.answered
                    else "OPEN"
                ),
            }
        )
    return {
        "application_mode": "AS_IS" if unresolved else "REVIEWED",
        "unresolved_at_apply_count": len(unresolved),
        "unresolved_at_apply": unresolved,
        # The digest proves which response state was visible at approval while
        # keeping unapplied free-form response text out of checkpoint metadata.
        "application_workbench_uid": (workbench.uid if workbench is not None else None),
        "application_workbench_response_digest": (
            atomize_workbench_response_digest(workbench)
            if workbench is not None
            else None
        ),
    }


def _record_atomize_workbench_application(
    *,
    store: MemoryStore,
    analysis: AtomizeAnalysisSession,
    workbench,
    output_context_name: str,
) -> None:
    """Persist Source-owned terminal state after the Context checkpoint exists."""

    if workbench is None:
        return
    checkpoint_uid = next(
        (
            checkpoint.get("uid")
            for checkpoint in store.list_checkpoints(output_context_name)
            if checkpoint.get("command") == "atomize"
            and isinstance(checkpoint.get("args"), dict)
            and checkpoint["args"].get("analysis_uid") == analysis.uid
        ),
        None,
    )
    if not isinstance(checkpoint_uid, str):
        raise AtomizeImpactError(
            "Atomize applied but its application checkpoint could not be found."
        )
    latest = store.load_atomize_workbench(analysis)
    if latest is None or latest.uid != workbench.uid:
        raise AtomizeImpactError(
            "Atomize applied but its reviewed workbench changed before the "
            "terminal receipt could be saved."
        )
    # An explicit one-shot --save-as chooses its Output after the workbench;
    # retain that actual destination before freezing the terminal receipt.
    latest.output_context_name = output_context_name
    latest.record_application(
        output_context_name=output_context_name,
        checkpoint_uid=checkpoint_uid,
    )
    store.save_atomize_workbench(latest)


def _inbound_split_references(
    store: MemoryStore,
    session: AtomizeAnalysisSession,
) -> list[tuple[str, MemoryRef]]:
    split_uids = {
        item.memory_uid for item in session.items if item.classification == "COMPOSITE"
    }
    if not split_uids:
        return []
    inbound: list[tuple[str, MemoryRef]] = []
    # A destructive split needs proof that every ordinary owner was examined.
    # Human navigation catalogs intentionally omit malformed records, so this
    # safety scan uses the strict direct graph instead.
    for context in store.load_direct_context_graph_strict():
        context_name = context.name
        for item in context.iter_items():
            if (
                isinstance(item, MemoryRef)
                and item.target_context_uid == session.context_uid
                and item.target_memory_uid in split_uids
            ):
                inbound.append((context_name, item))
    return inbound


def _render_apply_result(
    *,
    session: AtomizeAnalysisSession,
    context_name: str,
    result,
    created: bool,
    unresolved_at_apply_count: int,
) -> None:
    action = "Created and atomized" if created else "Applied atomize analysis to"
    typer.secho(
        f"{action} '{context_name}' from analysis [{session.uid[:8]}].",
        fg=typer.colors.GREEN,
        bold=True,
    )
    typer.echo(
        f"  {result.split_count} "
        f"{'split' if result.split_count == 1 else 'splits'} "
        f"-> {result.child_count} children"
    )
    typer.echo(f"  {result.preserved_count} Memories preserved in place")
    if unresolved_at_apply_count:
        typer.secho(
            f"  Applied as is with {unresolved_at_apply_count} unresolved "
            f"{'finding' if unresolved_at_apply_count == 1 else 'findings'} "
            "recorded",
            fg=typer.colors.YELLOW,
        )
    for item in result.items:
        if item.classification != "COMPOSITE":
            continue
        typer.echo(
            f"  [{item.source_uid[:8]}] -> "
            + ", ".join(f"[{uid[:8]}]" for uid in item.result_uids)
        )
    if created:
        typer.echo(
            "Two checkpoints created: the source-based initial state and "
            "the atomized state."
        )
        typer.echo(f"Switched to '{context_name}'.")
    else:
        typer.echo("One Context checkpoint created. The saved analysis remains linked.")


def _present_workbench(
    *,
    store: MemoryStore,
    analysis: AtomizeAnalysisSession,
    workbench,
    show_all: bool,
    workflow_actions: bool = True,
    application_complete: bool = False,
) -> ResolutionWorkbenchAction | None:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        typer.echo(
            render_atomize_workbench_snapshot(
                workbench,
                analysis,
                show_all=show_all,
            )
        )
        return None
    try:
        from memcommit.commands.resolution_workbench_shell import (
            ResolutionDestination,
        )

        planned_output = workbench.output_context_name or analysis.context_name

        def validate_destination(name: str) -> None:
            if name == analysis.context_name:
                raise ValueError(
                    "A distinct Atomize Output cannot be changed to the Input "
                    "Context from Save Location."
                )
            store.assert_context_creatable(name)

        result = run_atomize_workbench_shell(
            workbench,
            analysis,
            save=store.save_atomize_workbench,
            workflow_actions=workflow_actions,
            application_complete=application_complete,
            destination=(
                ResolutionDestination(
                    value=planned_output,
                    state="NOT CREATED",
                    detail=(
                        "Enter to change this exact new Context name before "
                        "Review and Apply."
                    ),
                    validate=validate_destination,
                    context_names=tuple(store.list_context_names()),
                    current_context=store.current_context_name(),
                )
                if workflow_actions and planned_output != analysis.context_name
                else None
            ),
        )
        return result if isinstance(result, ResolutionWorkbenchAction) else None
    except ReviewCancelled:
        typer.echo("Atomize workbench saved. No Memory changes applied.")
        return None


def _materialize_reviewed_workbench(
    *,
    store: MemoryStore,
    context,
    analysis: AtomizeAnalysisSession,
    workbench,
):
    """Create one reviewed proposal while freezing its response identity."""
    declared_frames, declared_frame_origins = atomize_workbench_declared_frames(
        workbench,
        analysis,
    )
    if not declared_frames:
        raise AtomizeImpactError(
            "The workbench has no single-Memory response to incorporate. "
            "Pairwise conflict responses remain staged for reconcile."
        )
    source_review_uid = workbench.uid
    source_review_digest = atomize_workbench_response_digest(workbench)

    def validate_before_save() -> None:
        latest = store.load_atomize_workbench(analysis)
        if (
            latest is None
            or latest.uid != source_review_uid
            or atomize_workbench_response_digest(latest) != source_review_digest
        ):
            raise AtomizeImpactError(
                "The atomize workbench changed while reviewed materialization "
                "was running; no proposal was saved."
            )

    with progressing_provider_factory(
        "ATOMIZE",
        "incorporating saved responses",
        connect_codex_chatgpt_provider,
    ) as provider_factory:
        return open_or_create_atomize_workbench(
            store=store,
            ctx=context,
            provider_factory=provider_factory,
            refresh=True,
            declared_frames=declared_frames,
            declared_frame_origins=declared_frame_origins,
            source_review_uid=source_review_uid,
            source_review_digest=source_review_digest,
            validate_before_save=validate_before_save,
        )


def _resume_selected_atomize(
    *,
    store: MemoryStore,
    analysis_uid: str,
    show_all: bool,
) -> None:
    """Open one frozen saved artifact without a create/refresh fallback."""
    analysis = load_saved_atomize_analysis(store, analysis_uid)
    context, applied = revalidate_saved_atomize_analysis(store, analysis)
    workbench = store.load_atomize_workbench(analysis)
    if workbench is None:
        raise AtomizeImpactError(
            "The saved atomize workbench is unavailable. Open the Context "
            "explicitly if you want to create fresh workbench state."
        )
    planned_output = workbench.output_context_name or analysis.context_name
    applied = applied or atomize_planned_output_was_applied(
        store,
        analysis,
        planned_output,
    )
    grounding = store.load_atomize_grounding_session(context.uid)
    if (
        not applied
        and grounding is not None
        and grounding.state
        in {
            "AWAITING_REPLY",
            "READY_TO_APPLY",
        }
    ):
        assert_current_grounding_bindings(
            grounding,
            context,
            analysis,
            workbench,
        )
        typer.echo(render_grounding_session(grounding, analysis))
        typer.secho(
            "Resumed without calling the semantic provider.",
            fg=typer.colors.CYAN,
        )
        return
    action = _present_workbench(
        store=store,
        analysis=analysis,
        workbench=workbench,
        show_all=show_all,
        workflow_actions=not applied,
        application_complete=applied,
    )
    if action is not None and action.kind in {
        "SUBMIT_ALL",
        "INCORPORATE_AND_APPLY",
    }:
        opened = _materialize_reviewed_workbench(
            store=store,
            context=context,
            analysis=analysis,
            workbench=workbench,
        )
        if action.kind == "INCORPORATE_AND_APPLY":
            cmd(save=True, context_name=context.name, show_all=show_all)
            return
        _resume_selected_atomize(
            store=store,
            analysis_uid=opened.analysis.uid,
            show_all=show_all,
        )
        return
    if action is not None and action.kind == "CHANGE_DESTINATION":
        if action.destination is None:
            raise AtomizeImpactError("Atomize returned an empty save-location change.")
        updated = replace(workbench, output_context_name=action.destination)
        store.save_atomize_workbench(updated)
        _resume_selected_atomize(
            store=store,
            analysis_uid=analysis.uid,
            show_all=show_all,
        )
        return
    if action is not None and action.kind == "ACCEPT":
        cmd(save=True, context_name=context.name, show_all=show_all)
        return
    if applied:
        typer.secho(
            f"Saved analysis [{analysis.uid[:8]}]: APPLIED.",
            fg=typer.colors.GREEN,
            bold=True,
        )
    else:
        exact_prewarm = is_installed_atomize_prewarm(store, analysis)
        typer.secho(
            f"Saved analysis [{analysis.uid[:8]}]: "
            + (
                "EXACT PREWARM · CURRENT. "
                if exact_prewarm
                else "CURRENT. "
            )
            + "Resumed; the provider was not called.",
            fg=typer.colors.CYAN,
        )


def _apply_to_new_context(
    *,
    store: MemoryStore,
    source_name: str,
    destination_name: str,
    session: AtomizeAnalysisSession,
    expected_current: str | None,
    application_audit: dict[str, object],
):
    """Create an init-like copy, then apply one saved preview to that copy."""
    if store.context_exists(destination_name):
        raise AtomizeImpactError(f"Context '{destination_name}' already exists.")

    # Resolve normal refs only after the direct-only preview has been verified.
    # Query-only refs remain opaque. ops.branch gives the destination a fresh
    # Context identity while preserving the source frame's direct Memory UIDs.
    source = store.load_for_update(source_name)
    source_digest = context_record_digest(source)
    destination = ops.branch(source, destination_name)
    created = False
    try:
        # Persist the unmodified source frame first. This makes save-as
        # inspectable as original state -> atomized state without copying the
        # source Context's unrelated checkpoint history.
        store.create_context_with_sources(
            destination,
            AutoCheckpoint(
                command="init",
                args={
                    "name": destination_name,
                    "source_context": {
                        "uid": source.uid,
                        "name": source.name,
                    },
                    "source_analysis_uid": session.uid,
                    "memory_uids": [
                        item.uid
                        for item in destination.iter_items()
                        if isinstance(item, Memory)
                    ],
                },
                description=(
                    f"Initialized '{destination_name}' from '{source_name}' "
                    f"before applying atomize [{session.uid[:8]}]"
                ),
            ),
            source_bindings=((source_name, source.uid, source_digest),),
        )
        created = True

        destination_session = replace(
            session,
            context_uid=destination.uid,
            context_name=destination.name,
            context_digest=direct_context_digest(destination),
        )
        store.save_atomize_analysis(destination_session)
        result = apply_atomize_analysis(destination, destination_session)
        store.save(
            destination,
            AutoCheckpoint(
                command="atomize",
                args={
                    "analysis_uid": destination_session.uid,
                    "ruleset_version": destination_session.ruleset_version,
                    "source_review_uid": (destination_session.source_review_uid),
                    "source_review_digest": (destination_session.source_review_digest),
                    "declared_frame_count": len(destination_session.declared_frames),
                    "split_count": result.split_count,
                    "child_count": result.child_count,
                    "preserved_count": result.preserved_count,
                    **application_audit,
                    "trace": result.trace_metadata(),
                },
                description=(
                    f"Applied atomize [{destination_session.uid[:8]}]: "
                    f"{result.split_count} splits -> {result.child_count} "
                    f"children; {result.preserved_count} preserved; "
                    f"{application_audit['unresolved_at_apply_count']} "
                    "unresolved at apply"
                ),
            ),
        )
        store.set_current_context_if(
            expected_current,
            destination.name,
            expected_context_uid=destination.uid,
            expected_context_digest=destination._store_digest or "",
        )
        return destination_session, result
    except Exception as error:
        if created:
            # Publication is observable even when the destination itself has
            # not changed. Deleting it by name could strand a concurrent
            # reference, so preserve the exact partial result for inspection.
            raise AtomizeImpactError(
                f"Atomize save-as failed ({error}); destination "
                f"'{destination.name}' was preserved for manual inspection "
                "and the source was not changed."
            ) from error
        raise


def cmd(
    save: Annotated[
        bool,
        typer.Option(
            "--save",
            help="Apply the current saved preview as one checkpoint",
        ),
    ] = False,
    save_as: Annotated[
        Optional[str],
        typer.Option(
            "--save-as",
            metavar="CONTEXT",
            help=(
                "Create an init-like Context from the source frame, apply the "
                "preview there, and switch to it"
            ),
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Context to inspect or atomize (defaults to current)",
        ),
    ] = None,
    output_name: Annotated[
        Optional[str],
        typer.Option(
            "--output",
            help=(
                "Persist the Atomize session's Output Context plan; use the "
                "Input name for in-place output or a new exact name"
            ),
        ),
    ] = None,
    show_all: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Show saved ATOMIC items as well as split/review items",
        ),
    ] = False,
    sessions: Annotated[
        bool,
        typer.Option(
            "--sessions",
            help="Enter the interactive Atomize session launcher",
        ),
    ] = False,
    evaluate: Annotated[
        Optional[str],
        typer.Option(
            "--evaluate",
            metavar="ISSUE",
            help=(
                "Start the issue-scoped directional meld (informally, atomic "
                "meld) for a visible issue number or unique issue/source uid "
                "prefix"
            ),
        ),
    ] = None,
    comment: Annotated[
        Optional[str],
        typer.Option(
            "--comment",
            help=(
                "Initial context/comment for --evaluate; prompted in a TTY when omitted"
            ),
        ),
    ] = None,
    reply: Annotated[
        Optional[str],
        typer.Option(
            "--reply",
            help="Confirm, correct, retract, or extend the open dialogue",
        ),
    ] = None,
    revision: Annotated[
        Optional[str],
        typer.Option(
            "--revision",
            help=(
                "How --reply relates to the prior turn: confirm, extend, "
                "correct, or retract"
            ),
        ),
    ] = None,
    accept_grounding_flag: Annotated[
        bool,
        typer.Option(
            "--accept-grounding",
            help="Apply the exact ready grounding proposal as one checkpoint",
        ),
    ] = False,
    keep_review_only: Annotated[
        bool,
        typer.Option(
            "--keep-review-only",
            help="Close the dialogue as evidence without changing Memories",
        ),
    ] = False,
) -> None:
    """Inspect a preview, mutate in place, or save an atomized new Context."""
    grounding_action_count = sum(
        (
            evaluate is not None,
            reply is not None,
            accept_grounding_flag,
            keep_review_only,
        )
    )
    if save and save_as is not None:
        typer.secho(
            "Atomize error: use either --save or --save-as, not both.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if output_name is not None and (save or save_as is not None):
        typer.secho(
            "Atomize error: --output plans a shared session; apply that "
            "session separately with --save (or use --save-as directly).",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if sessions and (
        save
        or save_as is not None
        or context_name is not None
        or output_name is not None
        or grounding_action_count
        or comment is not None
        or revision is not None
    ):
        typer.secho(
            "Atomize error: --sessions cannot be combined with a Context, "
            "mutation, or grounding action.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if grounding_action_count > 1:
        typer.secho(
            "Atomize error: use only one grounding action at a time.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if grounding_action_count and (save or save_as is not None):
        typer.secho(
            "Atomize error: grounding actions cannot be combined with "
            "--save or --save-as.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if grounding_action_count and output_name is not None:
        typer.secho(
            "Atomize error: --output cannot be combined with a grounding action.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if comment is not None and evaluate is None:
        typer.secho(
            "Atomize error: --comment requires --evaluate.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if revision is not None and reply is None:
        typer.secho(
            "Atomize error: --revision requires --reply.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)

    store = MemoryStore(create=False)
    try:
        browse_by_default = (
            _interactive_terminal()
            and not sessions
            and not save
            and save_as is None
            and context_name is None
            and output_name is None
            and grounding_action_count == 0
            and comment is None
            and revision is None
        )
        if sessions or browse_by_default:
            receipt = choose_atomize_session(store, show_all=show_all)
            if receipt is None:
                typer.echo("Atomize selection ended; no analysis was opened.")
                return
            if isinstance(receipt, SessionNewReceipt):
                setup = choose_atomize_setup(store)
                if setup is None:
                    typer.echo("New Atomize cancelled; no analysis was opened.")
                    return
                cmd(
                    context_name=setup.input_name,
                    output_name=setup.output_name,
                    show_all=show_all,
                )
                return
            _resume_selected_atomize(
                store=store,
                analysis_uid=receipt.key,
                show_all=show_all,
            )
            return
        context_snapshot = ContextOperandSnapshot.capture(store)
        name = context_snapshot.resolve_or_current(context_name)
        if not name:
            raise AtomizeImpactError(
                "No current context. Pass --context or run 'mem init <name>' first."
            )
        direct_ctx = store.load_direct(name)
        if output_name is not None and output_name != name:
            # A distinct Atomize Output is require-new. Validate before a
            # provider can be connected so setup cannot create semantic work
            # for an impossible or already occupied destination.
            store.assert_context_creatable(output_name)
        session = store.load_atomize_analysis(direct_ctx.uid)

        grounding = store.load_atomize_grounding_session(direct_ctx.uid)
        if keep_review_only:
            grounding = keep_grounding_review_only(
                store=store,
                context_uid=direct_ctx.uid,
            )
            typer.echo(render_grounding_session(grounding, session))
            return

        if (
            grounding_action_count == 0
            and grounding is not None
            and grounding.state in {"AWAITING_REPLY", "READY_TO_APPLY"}
        ):
            if save or save_as is not None:
                raise AtomizeGroundingCommandError(
                    "An atomize grounding dialogue is still open. Reply to "
                    "it, apply its exact proposal, or keep it as review-only "
                    "before using --save or --save-as."
                )
            if session is None:
                raise AtomizeGroundingCommandError(
                    "The saved atomize grounding dialogue is stale because "
                    "its source analysis is unavailable."
                )
            workbench = store.load_atomize_workbench(session)
            if workbench is None:
                raise AtomizeGroundingCommandError(
                    "The saved atomize grounding dialogue is stale because "
                    "its source workbench is unavailable."
                )
            # A provider-free resume is still a claim that this screen
            # describes the current Context. Refuse that claim when any bound
            # input changed rather than combining an old assessment with a new
            # issue projection.
            assert_current_grounding_bindings(
                grounding,
                direct_ctx,
                session,
                workbench,
            )
            typer.echo(render_grounding_session(grounding, session))
            typer.secho(
                "Resumed without calling the semantic provider.",
                fg=typer.colors.CYAN,
            )
            return

        if accept_grounding_flag:
            if session is None:
                raise AtomizeImpactError(
                    f"No saved atomize analysis exists for '{name}'."
                )
            workbench = store.load_atomize_workbench(session)
            if workbench is None:
                raise AtomizeGroundingCommandError(
                    "The atomize workbench bound to this grounding dialogue "
                    "is unavailable."
                )
            result = accept_grounding(
                store=store,
                ctx=direct_ctx,
                analysis=session,
                workbench=workbench,
            )
            grounding = store.load_atomize_grounding_session(direct_ctx.uid)
            assert grounding is not None
            typer.echo(render_grounding_session(grounding, session))
            if result.recovered:
                typer.secho(
                    "The prior application was recovered; no duplicate "
                    "checkpoint was created.",
                    fg=typer.colors.YELLOW,
                )
            else:
                typer.secho(
                    f"Applied {result.change_count} grounded "
                    f"{'change' if result.change_count == 1 else 'changes'} "
                    f"in checkpoint [{result.checkpoint_uid[:8]}].",
                    fg=typer.colors.GREEN,
                    bold=True,
                )
                typer.echo(
                    "The saved atomize analysis is now stale; refresh it "
                    "explicitly before further review."
                )
            return

        if grounding_action_count:
            if session is None:
                raise AtomizeImpactError(
                    f"No saved atomize analysis exists for '{name}'. "
                    "Run 'mem impact atomize' or 'mem atomize' first."
                )
            if not atomize_analysis_matches_context(session, direct_ctx):
                raise AtomizeImpactError(
                    "Saved atomize analysis is stale. Run "
                    "'mem impact atomize --refresh' before grounding it."
                )
            workbench = store.load_atomize_workbench(session)
            if workbench is None:
                workbench = create_atomize_workbench(session)
                store.save_atomize_workbench(workbench)

            if evaluate is not None:
                initial_comment = comment
                if initial_comment is None:
                    if not sys.stdin.isatty() or not sys.stdout.isatty():
                        raise AtomizeGroundingCommandError(
                            "--comment is required with --evaluate outside "
                            "an interactive terminal."
                        )
                    initial_comment = typer.prompt(
                        "Refine, comment, or enter a different reading"
                    )
                grounding = start_grounding(
                    store=store,
                    ctx=direct_ctx,
                    analysis=session,
                    workbench=workbench,
                    selector=evaluate,
                    comment=initial_comment,
                    provider_factory=connect_codex_chatgpt_provider,
                )
                typer.echo(render_grounding_session(grounding, session))
                return

            if reply is not None:
                grounding = reply_to_grounding(
                    store=store,
                    ctx=direct_ctx,
                    analysis=session,
                    workbench=workbench,
                    reply=reply,
                    revision=revision or "extend",
                    provider_factory=connect_codex_chatgpt_provider,
                )
                typer.echo(render_grounding_session(grounding, session))
                return

        applying = save or save_as is not None
        if not applying:
            if session is not None and (
                atomize_analysis_was_applied(store, direct_ctx, session.uid)
                or atomize_workbench_was_applied(store, session)
            ):
                workbench = store.load_atomize_workbench(session)
                if workbench is None:
                    # A save-as Output owns an applied analysis copy for
                    # provenance, not a second mutable shared session. Build
                    # only the read-only presentation projection here; saving
                    # it would make the session launcher observe two owners
                    # for one analysis UID on the next invocation.
                    workbench = create_atomize_workbench(session)
                _present_workbench(
                    store=store,
                    analysis=session,
                    workbench=workbench,
                    show_all=show_all,
                    workflow_actions=False,
                    application_complete=True,
                )
                typer.secho(
                    f"Saved analysis [{session.uid[:8]}]: APPLIED.",
                    fg=typer.colors.GREEN,
                    bold=True,
                )
                return
            atomize_prewarm = (
                find_declared_atomize_prewarm(
                    store=store,
                    context=direct_ctx,
                )
                if session is None
                else None
            )
            effective_output_name = (
                output_name
                or (
                    atomize_prewarm.output_context_name
                    if atomize_prewarm is not None
                    else None
                )
            )
            with progressing_provider_factory(
                "ATOMIZE",
                "analyzing memory structure",
                connect_codex_chatgpt_provider,
            ) as provider_factory:
                opened = open_or_create_atomize_workbench(
                    store=store,
                    ctx=direct_ctx,
                    provider_factory=provider_factory,
                    output_context_name=effective_output_name,
                    prepared_analysis=(
                        atomize_prewarm.analysis
                        if atomize_prewarm is not None
                        else None
                    ),
                )
            session = opened.analysis
            planned_output = opened.workbench.output_context_name or name
            planned_output_applied = atomize_planned_output_was_applied(
                store,
                session,
                planned_output,
            )
            if (
                planned_output != name
                and store.context_exists(planned_output)
                and not planned_output_applied
            ):
                raise AtomizeImpactError(
                    f"Planned atomize Output '{planned_output}' is occupied "
                    "by an unrelated Context. Choose a new Output before "
                    "continuing this session."
                )
            while True:
                action = _present_workbench(
                    store=store,
                    analysis=session,
                    workbench=opened.workbench,
                    show_all=show_all,
                    workflow_actions=not planned_output_applied,
                    application_complete=planned_output_applied,
                )
                if action is None:
                    break
                if action.kind in {"SUBMIT_ALL", "INCORPORATE_AND_APPLY"}:
                    opened = _materialize_reviewed_workbench(
                        store=store,
                        context=direct_ctx,
                        analysis=session,
                        workbench=opened.workbench,
                    )
                    session = opened.analysis
                    if action.kind == "INCORPORATE_AND_APPLY":
                        save = True
                        applying = True
                        break
                    continue
                if action.kind == "CHANGE_DESTINATION":
                    if action.destination is None:
                        raise AtomizeImpactError(
                            "Atomize returned an empty save-location change."
                        )
                    opened.workbench.output_context_name = action.destination
                    store.save_atomize_workbench(opened.workbench)
                    planned_output = action.destination
                    planned_output_applied = False
                    continue
                if action.kind == "ACCEPT":
                    save = True
                    applying = True
                    break
                raise AtomizeImpactError(
                    f"Unsupported Atomize workflow action '{action.kind}'."
                )
            if applying:
                # Continue through the ordinary --save validation and
                # checkpoint path below; the shared Apply row is its approval.
                pass
            else:
                exact_prewarm = (
                    not opened.created_analysis
                    and is_installed_atomize_prewarm(store, session)
                )
                typer.secho(
                    (
                        f"Saved analysis [{session.uid[:8]}]: APPLIED."
                        if planned_output_applied
                        else f"Saved analysis [{session.uid[:8]}]: CURRENT."
                        if opened.created_analysis
                        else (
                            f"Saved analysis [{session.uid[:8]}]: "
                            + (
                                "EXACT PREWARM · CURRENT. "
                                if exact_prewarm
                                else "CURRENT. "
                            )
                            + (
                                "Materialized on first use; the provider was not called."
                                if opened.materialized_prepared
                                else "Resumed; the provider was not called."
                            )
                        )
                    ),
                    fg=typer.colors.CYAN,
                )
                if planned_output_applied:
                    typer.echo(
                        f"Planned Output '{planned_output}' is already materialized."
                    )
                elif planned_output == name:
                    typer.echo(
                        "Apply the planned in-place Output with: mem atomize --save"
                    )
                else:
                    typer.echo(
                        "Apply the planned Output with: mem atomize --save\n"
                        f"  INPUT  {name}\n"
                        f"  OUTPUT {planned_output} · NOT CREATED"
                    )
                return

        if session is None:
            raise AtomizeImpactError(
                f"No saved atomize analysis exists for '{name}'. "
                "Run 'mem impact atomize' or 'mem atomize' first."
            )
        if session.context_uid != direct_ctx.uid or session.context_name != name:
            raise AtomizeImpactError(
                "The saved atomize analysis does not match this Context's identity."
            )
        already_applied = atomize_workbench_was_applied(
            store, session
        ) or atomize_analysis_was_applied(store, direct_ctx, session.uid)
        if save and already_applied:
            typer.secho(
                f"Atomize analysis [{session.uid[:8]}] is already applied; "
                "no new checkpoint was created.",
                fg=typer.colors.YELLOW,
            )
            return
        if not atomize_analysis_matches_context(session, direct_ctx):
            raise AtomizeImpactError(
                "Saved atomize analysis is stale. "
                "Run 'mem impact atomize --refresh' before saving."
            )
        workbench = store.load_atomize_workbench(session)
        planned_output = (
            workbench.output_context_name if workbench is not None else name
        )
        applying_planned_output = save and save_as is None and planned_output != name
        if applying_planned_output:
            save_as = planned_output
        if save_as is not None and store.context_exists(save_as):
            output_context = store.load_direct(save_as)
            output_analysis = store.load_atomize_analysis(output_context.uid)
            if (
                output_analysis is not None
                and output_analysis.uid == session.uid
                and atomize_planned_output_was_applied(store, session, save_as)
            ):
                typer.secho(
                    f"Atomize analysis [{session.uid[:8]}] is already "
                    f"applied to planned Output '{save_as}'; no new "
                    "checkpoint was created.",
                    fg=typer.colors.YELLOW,
                )
                return
            raise AtomizeImpactError(
                f"Planned atomize Output '{save_as}' already exists and is "
                "not the exact applied result of this session."
            )
        incorporable_response_count = _incorporable_workbench_response_count(
            session,
            workbench,
        )
        if (
            incorporable_response_count
            and workbench is not None
            and (
                session.source_review_uid != workbench.uid
                or session.source_review_digest
                != atomize_workbench_response_digest(workbench)
            )
        ):
            raise AtomizeImpactError(
                "Saved atomize workbench responses have not been "
                "incorporated into this analysis. Run "
                "'mem impact atomize --with-review' before saving."
            )
        review = store.load_review_session()
        review_has_comments = (
            review is not None
            and review.kind == "atomize"
            and review.context_uid == direct_ctx.uid
            and atomize_review_declared_frames(review)
        )
        if review_has_comments and (
            session.source_review_uid != review.uid
            or session.source_review_digest != review_response_digest(review)
        ):
            if atomize_review_matches_analysis(
                review,
                direct_ctx,
                session,
            ):
                raise AtomizeImpactError(
                    "Saved atomize comments have not been incorporated into "
                    "this analysis. Run 'mem impact atomize --with-review' "
                    "before saving."
                )
            raise AtomizeImpactError(
                "Saved atomize comments belong to a stale or different "
                "analysis and cannot be incorporated into this preview. "
                "Start a new review with "
                "'mem review atomize --replace-review' to explicitly "
                "replace them before saving."
            )

        # A bare interactive session has already reviewed its planned Output
        # in the shared workbench immediately before Review and Apply. Keep
        # the standalone receipt only for an explicit one-shot --save-as,
        # which does not open that saved-session surface.
        if (
            save_as is not None
            and _interactive_terminal()
            and not applying_planned_output
        ):
            from memcommit.commands.save_location_review import (
                review_save_location,
            )

            reviewed_destination = review_save_location(
                save_as,
                validate=store.assert_context_creatable,
                apply_label="create atomized Context",
            )
            if reviewed_destination is None:
                typer.echo(
                    "Aborted — the saved atomize analysis remains available; "
                    "no Context changes made."
                )
                return
            save_as = reviewed_destination

        application_audit = _atomize_application_audit(session, workbench)
        if save_as is not None:
            applied_session, result = _apply_to_new_context(
                store=store,
                source_name=name,
                destination_name=save_as,
                session=session,
                expected_current=context_snapshot.current_name,
                application_audit=application_audit,
            )
            applied_name = save_as
            created = True
        else:
            inbound = _inbound_split_references(store, session)
            if inbound:
                locations = ", ".join(
                    f"{owner}#{reference.uid[:8]}" for owner, reference in inbound
                )
                raise AtomizeImpactError(
                    "Cannot split a Memory with inbound memory references in "
                    f"version 1: {locations}."
                )

            # Saving a load_direct Context would omit embedded Context pointers.
            ctx = store.load_for_update(name)
            result = apply_atomize_analysis(ctx, session)
            store.save(
                ctx,
                AutoCheckpoint(
                    command="atomize",
                    args={
                        "analysis_uid": session.uid,
                        "ruleset_version": session.ruleset_version,
                        "source_review_uid": session.source_review_uid,
                        "source_review_digest": session.source_review_digest,
                        "declared_frame_count": len(session.declared_frames),
                        "split_count": result.split_count,
                        "child_count": result.child_count,
                        "preserved_count": result.preserved_count,
                        **application_audit,
                        "trace": result.trace_metadata(),
                    },
                    description=(
                        f"Applied atomize [{session.uid[:8]}]: "
                        f"{result.split_count} splits -> {result.child_count} "
                        f"children; {result.preserved_count} preserved; "
                        f"{application_audit['unresolved_at_apply_count']} "
                        "unresolved at apply"
                    ),
                ),
            )
            applied_session = session
            applied_name = ctx.name
            created = False
        _record_atomize_workbench_application(
            store=store,
            analysis=session,
            workbench=workbench,
            output_context_name=applied_name,
        )
    except (
        FileNotFoundError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        AtomizeImpactError,
        AtomizeWorkbenchError,
        AtomizeGroundingCommandError,
        QueryProviderError,
    ) as error:
        typer.secho(f"Atomize error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    _render_apply_result(
        session=applied_session,
        context_name=applied_name,
        result=result,
        created=created,
        unresolved_at_apply_count=int(application_audit["unresolved_at_apply_count"]),
    )
