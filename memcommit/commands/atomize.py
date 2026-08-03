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
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.commands.review_shell import ReviewCancelled
from memcommit.context import AutoCheckpoint, Context, Memory, MemoryRef
from memcommit.review import (
    atomize_review_declared_frames,
    atomize_review_matches_analysis,
    direct_context_digest,
    review_response_digest,
)
from memcommit.store import MemoryStore, context_record_digest
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)


def _analysis_was_applied(
    store: MemoryStore,
    ctx: Context,
    analysis_uid: str,
) -> bool:
    current_digest = direct_context_digest(ctx)
    for checkpoint in store.list_checkpoints(ctx.name):
        args = checkpoint.get("args")
        trace = args.get("trace") if isinstance(args, dict) else None
        if not (
            isinstance(trace, dict)
            and trace.get("operation_id") == analysis_uid
        ):
            continue
        snapshot = checkpoint.get("snapshot")
        if not isinstance(snapshot, dict):
            continue
        try:
            checkpoint_ctx = Context.from_dict(snapshot)
        except (KeyError, TypeError):
            continue
        if (
            checkpoint_ctx.uid == ctx.uid
            and checkpoint_ctx.name == ctx.name
            and direct_context_digest(checkpoint_ctx) == current_digest
        ):
            return True
    return False


def _inbound_split_references(
    store: MemoryStore,
    session: AtomizeAnalysisSession,
) -> list[tuple[str, MemoryRef]]:
    split_uids = {
        item.memory_uid
        for item in session.items
        if item.classification == "COMPOSITE"
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
        typer.echo(
            "One Context checkpoint created. "
            "The saved analysis remains linked."
        )


def _present_workbench(
    *,
    store: MemoryStore,
    analysis: AtomizeAnalysisSession,
    workbench,
    show_all: bool,
) -> None:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        typer.echo(
            render_atomize_workbench_snapshot(
                workbench,
                analysis,
                show_all=show_all,
            )
        )
        return
    try:
        run_atomize_workbench_shell(
            workbench,
            analysis,
            save=store.save_atomize_workbench,
        )
    except ReviewCancelled:
        typer.echo("Atomize workbench saved. No Memory changes applied.")


def _apply_to_new_context(
    *,
    store: MemoryStore,
    source_name: str,
    destination_name: str,
    session: AtomizeAnalysisSession,
    expected_current: str | None,
):
    """Create an init-like copy, then apply one saved preview to that copy."""
    if store.context_exists(destination_name):
        raise AtomizeImpactError(
            f"Context '{destination_name}' already exists."
        )

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
                    "source_review_uid": (
                        destination_session.source_review_uid
                    ),
                    "source_review_digest": (
                        destination_session.source_review_digest
                    ),
                    "declared_frame_count": len(
                        destination_session.declared_frames
                    ),
                    "split_count": result.split_count,
                    "child_count": result.child_count,
                    "preserved_count": result.preserved_count,
                    "trace": result.trace_metadata(),
                },
                description=(
                    f"Applied atomize [{destination_session.uid[:8]}]: "
                    f"{result.split_count} splits -> {result.child_count} "
                    f"children; {result.preserved_count} preserved"
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
    show_all: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Show saved ATOMIC items as well as split/review items",
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
                "Initial context/comment for --evaluate; prompted in a TTY "
                "when omitted"
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
        context_snapshot = ContextOperandSnapshot.capture(store)
        name = context_snapshot.resolve_or_current(context_name)
        if not name:
            raise AtomizeImpactError(
                "No current context. Pass --context or run 'mem init <name>' first."
            )
        direct_ctx = store.load_direct(name)
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
            if session is not None and _analysis_was_applied(
                store,
                direct_ctx,
                session.uid,
            ):
                workbench = store.load_atomize_workbench(session)
                if workbench is None:
                    workbench = create_atomize_workbench(session)
                    store.save_atomize_workbench(workbench)
                _present_workbench(
                    store=store,
                    analysis=session,
                    workbench=workbench,
                    show_all=show_all,
                )
                typer.secho(
                    f"Saved analysis [{session.uid[:8]}]: APPLIED.",
                    fg=typer.colors.GREEN,
                    bold=True,
                )
                return
            opened = open_or_create_atomize_workbench(
                store=store,
                ctx=direct_ctx,
                provider_factory=connect_codex_chatgpt_provider,
            )
            session = opened.analysis
            _present_workbench(
                store=store,
                analysis=session,
                workbench=opened.workbench,
                show_all=show_all,
            )
            typer.secho(
                (
                    f"Saved analysis [{session.uid[:8]}]: CURRENT."
                    if opened.created_analysis
                    else (
                        f"Saved analysis [{session.uid[:8]}]: CURRENT. "
                        "Resumed; the provider was not called."
                    )
                ),
                fg=typer.colors.CYAN,
            )
            typer.echo(
                "Apply in place with: mem atomize --save\n"
                "Or preserve the source with: "
                "mem atomize --save-as NEW_CONTEXT"
            )
            return

        if session is None:
            raise AtomizeImpactError(
                f"No saved atomize analysis exists for '{name}'. "
                "Run 'mem impact atomize' or 'mem atomize' first."
            )
        if (
            session.context_uid != direct_ctx.uid
            or session.context_name != name
        ):
            raise AtomizeImpactError(
                "The saved atomize analysis does not match this Context's "
                "identity."
            )
        already_applied = _analysis_was_applied(
            store,
            direct_ctx,
            session.uid,
        )
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
        workbench_frames = {}
        if workbench is not None and workbench.answered_count:
            (
                workbench_frames,
                _workbench_origins,
            ) = atomize_workbench_declared_frames(
                workbench,
                session,
            )
        if workbench_frames and (
            session.source_review_uid != workbench.uid
            or session.source_review_digest
            != atomize_workbench_response_digest(workbench)
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
                or session.source_review_digest
                != review_response_digest(review)
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

        if save_as is not None:
            applied_session, result = _apply_to_new_context(
                store=store,
                source_name=name,
                destination_name=save_as,
                session=session,
                expected_current=context_snapshot.current_name,
            )
            applied_name = save_as
            created = True
        else:
            inbound = _inbound_split_references(store, session)
            if inbound:
                locations = ", ".join(
                    f"{owner}#{reference.uid[:8]}"
                    for owner, reference in inbound
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
                        "declared_frame_count": len(
                            session.declared_frames
                        ),
                        "split_count": result.split_count,
                        "child_count": result.child_count,
                        "preserved_count": result.preserved_count,
                        "trace": result.trace_metadata(),
                    },
                    description=(
                        f"Applied atomize [{session.uid[:8]}]: "
                        f"{result.split_count} splits -> {result.child_count} "
                        f"children; {result.preserved_count} preserved"
                    ),
                ),
            )
            applied_session = session
            applied_name = ctx.name
            created = False
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
    )
