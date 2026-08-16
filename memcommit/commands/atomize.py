"""Inspect or explicitly apply the latest saved atomize analysis."""

from __future__ import annotations

import sys
from dataclasses import replace
from typing import Annotated, Optional

import typer

from memcommit.atomize import (
    AtomizeAnalysisSession,
    AtomizeImpactError,
    atomize_analysis_matches_context,
)
from memcommit.atomize_analysis_application import AtomizeAnalysisOpenRequest
from memcommit.atomize_analysis_runtime import execute_atomize_analysis_open
from memcommit.atomize_application import (
    AtomizePersistedApplyRequest,
    AtomizeSaveAsRequest,
)
from memcommit.atomize_runtime import (
    capture_atomize_session_snapshot,
    execute_atomize_save_as,
    execute_atomize_session_apply,
)
from memcommit.atomize_workbench import (
    AtomizeWorkbenchError,
    atomize_workbench_declared_frames,
    atomize_workbench_response_digest,
    create_atomize_workbench,
    project_atomize_workbench_findings,
)
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
from memcommit.review import (
    atomize_review_declared_frames,
    atomize_review_matches_analysis,
    review_response_digest,
)
from memcommit.store import MemoryStore
from memcommit.study_prewarm.atomize import is_installed_atomize_prewarm
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.resolution_workbench import ResolutionWorkbenchAction


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


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


def _render_apply_result(
    *,
    session: AtomizeAnalysisSession,
    context_name: str,
    result,
    created: bool,
    unresolved_at_apply_count: int,
    recovered_application: bool = False,
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
    if recovered_application:
        typer.secho(
            "  Recovered the exact prior checkpoint; no duplicate was created",
            fg=typer.colors.YELLOW,
        )
    if created:
        typer.echo(
            "One Atomize checkpoint created; no intermediate Context was "
            "published."
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
        return execute_atomize_analysis_open(
            AtomizeAnalysisOpenRequest(
                context=context,
                refresh=True,
                declared_frames=declared_frames,
                declared_frame_origins=declared_frame_origins,
                source_review_uid=source_review_uid,
                source_review_digest=source_review_digest,
                allow_prepared=False,
            ),
            store=store,
            provider_factory=provider_factory,
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
                "Create one final atomized Context from the source frame and "
                "switch to it"
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
            with progressing_provider_factory(
                "ATOMIZE",
                "analyzing memory structure",
                connect_codex_chatgpt_provider,
            ) as provider_factory:
                opened = execute_atomize_analysis_open(
                    AtomizeAnalysisOpenRequest(
                        context=direct_ctx,
                        output_context_name=output_name,
                        allow_prepared=session is None,
                    ),
                    store=store,
                    provider_factory=provider_factory,
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
        workbench = store.load_atomize_workbench(session)
        planned_output = (
            workbench.output_context_name if workbench is not None else name
        )
        applying_planned_output = save and save_as is None and planned_output != name
        if applying_planned_output:
            save_as = planned_output
        already_applied = atomize_workbench_was_applied(
            store, session
        ) or atomize_analysis_was_applied(store, direct_ctx, session.uid)
        recovering_missing_receipt = (
            save
            and save_as is None
            and already_applied
            and workbench is not None
            and workbench.application is None
        )
        if (
            save
            and save_as is None
            and already_applied
            and not recovering_missing_receipt
        ):
            typer.secho(
                f"Atomize analysis [{session.uid[:8]}] is already applied; "
                "no new checkpoint was created.",
                fg=typer.colors.YELLOW,
            )
            return
        if (
            not recovering_missing_receipt
            and not atomize_analysis_matches_context(session, direct_ctx)
        ):
            raise AtomizeImpactError(
                "Saved atomize analysis is stale. "
                "Run 'mem impact atomize --refresh' before saving."
            )
        if save_as is not None and store.context_exists(save_as):
            output_context = store.load_direct(save_as)
            output_analysis = store.load_atomize_analysis(output_context.uid)
            if (
                output_analysis is not None
                and output_analysis.uid == session.uid
                and atomize_planned_output_was_applied(store, session, save_as)
            ):
                # Continue through the typed Save As boundary. It validates
                # the exact checkpoint and completes any missing Source
                # receipt/current selection without publishing another one.
                pass
            else:
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
            and not store.context_exists(save_as)
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

        recovered_application = False
        snapshot = capture_atomize_session_snapshot(
            store=store,
            analysis=session,
            expected_workbench=workbench,
        )
        if save_as is not None:
            applied = execute_atomize_save_as(
                AtomizeSaveAsRequest(
                    snapshot=snapshot,
                    destination_name=save_as,
                    expected_current=context_snapshot.current_name,
                ),
                store=store,
            )
            applied_session = applied.output_analysis
            result = applied.materialization.result
            applied_name = applied.materialization.context_name
            created = True
            recovered_application = applied.recovered
            application_audit = applied.audit.checkpoint_fields()
        else:
            applied = execute_atomize_session_apply(
                AtomizePersistedApplyRequest(snapshot=snapshot),
                store=store,
            )
            result = applied.materialization.result
            applied_session = session
            applied_name = applied.materialization.context_name
            created = False
            recovered_application = applied.recovered
            application_audit = applied.audit.checkpoint_fields()
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
        recovered_application=recovered_application,
    )
