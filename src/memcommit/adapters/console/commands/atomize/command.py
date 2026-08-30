"""Inspect or explicitly apply the latest saved atomize analysis."""

from __future__ import annotations

import sys
from dataclasses import replace
from typing import Annotated, Optional

import typer

from memcommit.application.operations.atomize.domain import (
    AtomizeImpactError,
    atomize_analysis_matches_context,
)
from memcommit.application.operations.atomize.analysis_application import (
    AtomizeAnalysisOpenRequest,
)
from memcommit.application.operations.atomize.analysis_runtime import (
    execute_atomize_analysis_open,
)
from memcommit.application.operations.atomize.application import (
    AtomizeOutputPlanRequest,
    AtomizePersistedApplyRequest,
    AtomizeSaveAsRequest,
)
from memcommit.application.operations.atomize.runtime import (
    capture_atomize_session_snapshot,
    execute_atomize_output_plan_update,
    execute_atomize_save_as,
    execute_atomize_session_apply,
)
from memcommit.application.operations.atomize.workbench import (
    AtomizeWorkbenchError,
)
from memcommit.adapters.console.commands.atomize.receipt import (
    render_atomize_apply_result,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.adapters.console.commands.atomize.workbench.adapter import (
    present_atomize_workbench,
)
from memcommit.adapters.console.terminal.components.progress import progressing_provider_factory
from memcommit.adapters.console.commands.atomize.sessions import (
    atomize_analysis_was_applied,
    atomize_planned_output_was_applied,
    atomize_workbench_was_applied,
    choose_atomize_session,
    load_saved_atomize_analysis,
    revalidate_saved_atomize_analysis,
)
from memcommit.adapters.console.terminal.components.endpoint_setup.flows import choose_atomize_setup
from memcommit.adapters.console.terminal.components.operation_launcher.session import (
    SessionNewReceipt,
)
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
    choose_context_operand,
)
from memcommit.core.context_targeting.loading import (
    DirectMemoryAmbiguityError,
    resolve_local_context_memory_target,
)
from memcommit.core.context_targeting.memory_focus import is_memory_uid_prefix
from memcommit.core.context_targeting.model import (
    ContextTarget,
    DirectMemoryLocator,
    DirectMemoryTarget,
    ExistingContextOperand,
)
from memcommit.core.context_targeting.resolution import (
    parse_auto_typed_context_memory_operand,
)
from memcommit.persistence.store import MemoryStore
from memcommit.study_scenarios.legacy.prewarm.atomize import (
    is_installed_atomize_prewarm,
)
from memcommit.providers.subscription import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


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
    if applied:
        typer.echo(f"ATOMIZE APPLIED · {planned_output}")
        typer.echo(f"ANALYSIS · {analysis.uid}")
        typer.echo(f"REVIEW · mem review atomize --context {planned_output}")
        return
    action = present_atomize_workbench(
        store=store,
        analysis=analysis,
        workbench=workbench,
        show_all=show_all,
        workflow_actions=not applied,
        application_complete=applied,
    )
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
            + ("EXACT PREWARM · CURRENT. " if exact_prewarm else "CURRENT. ")
            + "Resumed; the provider was not called.",
            fg=typer.colors.CYAN,
        )


def cmd(
    context_operand: Annotated[
        Optional[str],
        typer.Argument(
            metavar="TARGET",
            help=(
                "Auto-typed existing Context, Memory UID/prefix, or "
                "CONTEXT:UID (defaults to current Context)"
            ),
        ),
    ] = None,
    save: Annotated[
        bool,
        typer.Option(
            "--save",
            help="Apply an existing advanced Atomize session as one checkpoint",
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
            help="Context to atomize now (defaults to current)",
        ),
    ] = None,
    memory_selector: Annotated[
        Optional[str],
        typer.Option(
            "--memory",
            metavar="UID_OR_PREFIX",
            help=(
                "Analyze one direct Memory while keeping its Context neighbors "
                "available only as non-actionable evidence"
            ),
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
    refresh: Annotated[
        bool,
        typer.Option(
            "--refresh",
            help=(
                "Start a new semantic analysis even when the same request "
                "already has a saved or applied session"
            ),
        ),
    ] = False,
) -> None:
    """Atomize the current Context or use an explicit advanced route."""
    try:
        parsed_operand = (
            parse_auto_typed_context_memory_operand(context_operand)
            if context_operand is not None
            else None
        )
        if (
            isinstance(parsed_operand, ExistingContextOperand)
            and context_name is None
            and is_memory_uid_prefix(context_operand)
        ):
            early_store = MemoryStore(create=False)
            early_snapshot = ContextOperandSnapshot.capture(early_store)
            try:
                early_target = resolve_local_context_memory_target(
                    early_store,
                    context_operand,
                    current=early_snapshot.current_name,
                )
            except FileNotFoundError:
                early_target = None
            except DirectMemoryAmbiguityError:
                # Preserve Memory-mode validation, then let the execution
                # boundary report the complete owner catalog as a runtime
                # targeting failure before provider connection.
                parsed_operand = DirectMemoryLocator(context_operand)
                early_target = None
            if isinstance(early_target, DirectMemoryTarget):
                parsed_operand = DirectMemoryLocator(
                    early_target.memory_uid,
                    early_target.context_name,
                )
        if isinstance(parsed_operand, DirectMemoryLocator):
            if context_name is not None:
                raise ValueError(
                    "Auto-typed Memory cannot be combined with --context; use "
                    "CONTEXT:UID or --context CONTEXT --memory UID."
                )
            if memory_selector is not None:
                raise ValueError(
                    "Memory was supplied both positionally and with --memory."
                )
            context_name = parsed_operand.context_locator
            memory_selector = parsed_operand.memory_selector
        else:
            positional_context = (
                parsed_operand.locator
                if isinstance(parsed_operand, ExistingContextOperand)
                else None
            )
            context_name = choose_context_operand(
                positional_context,
                option=context_name,
            )
    except ValueError as error:
        typer.secho(
            f"Atomize error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    auto_apply_exact_context = (
        not save
        and save_as is None
        and memory_selector is None
        and output_name is None
        and not show_all
        and not sessions
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
        or memory_selector is not None
        or output_name is not None
        or refresh
    ):
        typer.secho(
            "Atomize error: --sessions cannot be combined with a Context, "
            "mutation, or refresh action.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if refresh and (save or save_as is not None):
        typer.secho(
            "Atomize error: --refresh starts new analysis work and cannot be "
            "combined with an apply action.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if memory_selector is not None and (save or save_as is not None):
        typer.secho(
            "Atomize error: --memory selects a new analysis scope and cannot "
            "be combined with apply actions.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)

    store = MemoryStore(create=False)
    try:
        if sessions:
            receipt = choose_atomize_session(store, show_all=show_all)
            if receipt is None:
                typer.echo("Atomize selection ended; no analysis was opened.")
                return
            if isinstance(receipt, SessionNewReceipt):
                setup = choose_atomize_setup(store)
                if setup is None:
                    typer.echo("New Atomize cancelled; no analysis was opened.")
                    return
                start_kwargs = {
                    "context_name": setup.input_name,
                    "output_name": setup.output_name,
                    "show_all": show_all,
                    # New means a new work unit even when setup selects the
                    # same Context and scope as a terminal latest session.
                    "refresh": True,
                }
                if setup.input_memory_uid is not None:
                    start_kwargs["memory_selector"] = setup.input_memory_uid
                cmd(**start_kwargs)
                return
            _resume_selected_atomize(
                store=store,
                analysis_uid=receipt.key,
                show_all=show_all,
            )
            return
        context_snapshot = ContextOperandSnapshot.capture(store)
        if context_operand is not None:
            auto_target = resolve_local_context_memory_target(
                store,
                context_operand,
                current=context_snapshot.current_name,
            )
            if isinstance(auto_target, DirectMemoryTarget):
                context_name = auto_target.context_name
                memory_selector = auto_target.memory_uid
            else:
                assert isinstance(auto_target, ContextTarget)
                context_name = auto_target.context_name
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
        applied_exact_prewarm = False

        applying = save or save_as is not None or auto_apply_exact_context
        if auto_apply_exact_context:
            existing_applied = (
                not refresh
                and session is not None
                and (
                    atomize_analysis_was_applied(store, direct_ctx, session.uid)
                    or atomize_workbench_was_applied(store, session)
                )
            )
            if not existing_applied:
                # Bare Atomize means the complete current Context. Opening
                # through the shared boundary reuses an exact whole-Context
                # analysis, but replaces an older focused analysis with the
                # requested complete scope before any mutation can begin.
                with progressing_provider_factory(
                    "ATOMIZE",
                    "analyzing memory structure",
                    connect_codex_chatgpt_provider,
                ) as provider_factory:
                    opened = execute_atomize_analysis_open(
                        AtomizeAnalysisOpenRequest(
                            context=direct_ctx,
                            refresh=refresh,
                            allow_prepared=session is None and not refresh,
                        ),
                        store=store,
                        provider_factory=provider_factory,
                    )
                session = opened.analysis
                applied_exact_prewarm = opened.materialized_prepared
            # This is intentionally set only after the durable analysis pair
            # exists. The ordinary Apply path below still owns freshness,
            # reference, audit, checkpoint, compensation, and retry checks.
            save = True
        if not applying:
            if (
                memory_selector is None
                and not refresh
                and session is not None
                and (
                    atomize_analysis_was_applied(store, direct_ctx, session.uid)
                    or atomize_workbench_was_applied(store, session)
                )
            ):
                typer.echo(f"ATOMIZE APPLIED · {name}")
                typer.echo(f"ANALYSIS · {session.uid}")
                typer.echo(f"REVIEW · mem review atomize --context {name}")
                return
            with progressing_provider_factory(
                "ATOMIZE",
                "analyzing memory structure",
                connect_codex_chatgpt_provider,
            ) as provider_factory:
                opened = execute_atomize_analysis_open(
                    AtomizeAnalysisOpenRequest(
                        context=direct_ctx,
                        refresh=refresh,
                        output_context_name=output_name,
                        memory_selector=memory_selector,
                        allow_prepared=session is None and not refresh,
                    ),
                    store=store,
                    provider_factory=provider_factory,
                )
            session = opened.analysis
            applied_exact_prewarm = opened.materialized_prepared
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
                action = present_atomize_workbench(
                    store=store,
                    analysis=session,
                    workbench=opened.workbench,
                    show_all=show_all,
                    workflow_actions=not planned_output_applied,
                    application_complete=planned_output_applied,
                )
                if action is None:
                    break
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
                        f"  OUTPUT {planned_output} · CREATE ON APPLY"
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
        already_applied = atomize_workbench_was_applied(
            store, session
        ) or atomize_analysis_was_applied(store, direct_ctx, session.uid)
        if (
            auto_apply_exact_context
            and not already_applied
            and workbench is not None
            and workbench.output_context_name != name
        ):
            # Bare Atomize has one unambiguous destination: the Context that
            # was current at command start. An older setup-screen Output plan
            # must not silently turn this direct command into Save As.
            accepted = capture_atomize_session_snapshot(
                store=store,
                analysis=session,
                expected_workbench=workbench,
            )
            updated = execute_atomize_output_plan_update(
                AtomizeOutputPlanRequest(
                    snapshot=accepted,
                    output_context_name=name,
                ),
                store=store,
            )
            workbench = updated.snapshot.workbench
        planned_output = (
            workbench.output_context_name if workbench is not None else name
        )
        applying_planned_output = save and save_as is None and planned_output != name
        if applying_planned_output:
            save_as = planned_output
        recovering_missing_receipt = (
            save
            and save_as is None
            and already_applied
            and workbench is not None
            and workbench.application is None
        )
        if (
            save_as is not None
            and already_applied
            and workbench is not None
            and workbench.application is not None
            and workbench.application.output_context_name == save_as
            and context_snapshot.current_name == save_as
        ):
            typer.secho(
                f"Atomize analysis [{session.uid[:8]}] is already applied; "
                "no new checkpoint was created.",
                fg=typer.colors.YELLOW,
            )
            return
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
        if not recovering_missing_receipt and not atomize_analysis_matches_context(
            session, direct_ctx
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
            from memcommit.adapters.console.terminal.components.save_location_review import (
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
        # Apply may connect for Dedun discovery and final normal-form checks.
        # Start lazily so exact checkpoint recovery remains visibly silent.
        with progressing_provider_factory(
            "ATOMIZE",
            "normalizing atomized output",
            connect_codex_chatgpt_provider,
        ) as provider_factory:
            if save_as is not None:
                applied = execute_atomize_save_as(
                    AtomizeSaveAsRequest(
                        snapshot=snapshot,
                        destination_name=save_as,
                        expected_current=context_snapshot.current_name,
                    ),
                    store=store,
                    provider_factory=provider_factory,
                )
                applied_session = applied.output_analysis
                result = applied.materialization.result
                applied_name = applied.materialization.context_name
                created = True
                recovered_application = applied.recovered
                application_audit = applied.audit
            else:
                applied = execute_atomize_session_apply(
                    AtomizePersistedApplyRequest(snapshot=snapshot),
                    store=store,
                    provider_factory=provider_factory,
                )
                result = applied.materialization.result
                applied_session = session
                applied_name = applied.materialization.context_name
                created = False
                recovered_application = applied.recovered
                application_audit = applied.audit
    except (
        FileNotFoundError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        AtomizeImpactError,
        AtomizeWorkbenchError,
        QueryProviderError,
    ) as error:
        typer.secho(f"Atomize error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    render_atomize_apply_result(
        session=applied_session,
        context_name=applied_name,
        result=result,
        checkpoint_uid=applied.materialization.checkpoint_uid,
        created=created,
        audit=application_audit,
        recovered_application=recovered_application,
        exact_prewarm=applied_exact_prewarm,
    )
