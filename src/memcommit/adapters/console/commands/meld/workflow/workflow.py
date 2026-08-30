"""Console workflow orchestration for Meld application services."""

from __future__ import annotations

import sys

from memcommit.core.context import Context
from memcommit.core.context_targeting.loading import load_context_scope
from memcommit.core.context_targeting.memory_focus import (
    MemoryFocusError,
    resolve_memory_focus,
)
from memcommit.application.capabilities.authority.context_access import (
    ContextAccess,
    GrantedReadStore,
    revalidate_granted_context_binding,
    resolve_context_access,
)
from memcommit.adapters.console.terminal.components.command_wait import (
    run_command_wait,
)
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.granted_repository import (
    granted_artifact_contexts,
    load_granted_comparison_artifact,
    recursive_comparison_projection,
)
from memcommit.application.operations.meld.model import (
    MELD_INLINE_MEMORY_SCHEMA_VERSION,
    MELD_OWNER_AWARE_SCHEMA_VERSION,
    MELD_SCHEMA_VERSION,
    MeldFrame,
    MeldIssue,
    MeldSession,
    inline_meld_context,
    meld_canonical_digest,
)
from memcommit.application.operations.meld.restart import MeldRestartRequest
from memcommit.application.operations.meld.start import MeldStartRequest
from memcommit.application.capabilities.authority.source_use_policy import (
    analysis_retention,
    authorize_analysis_save,
    authorize_combination,
    authorize_derived_transfer,
)
from memcommit.adapters.console.commands.meld.workbench import run_meld_shell
from memcommit.adapters.console.commands.meld.sessions import (
    MeldSessionCatalogEntry,
    reload_selected_meld_session,
)
from memcommit.providers.subscription import (
    connect_codex_chatgpt_provider,
)
from memcommit.application.operations.profile.model import ProfileError
from memcommit.core.context_targeting.naming import validate_portable_context_name
from memcommit.application.capabilities.resolution.workbench import ResolutionNavigation
from memcommit.persistence.store import (
    MemoryStore,
    context_record_digest,
)

from memcommit.adapters.console.commands.meld.errors import MeldCommandError
from memcommit.adapters.console.commands.meld.interpretation import (
    InterpretedMeldCommand,
)
from memcommit.adapters.console.commands.meld.presentation import (
    _meld_wait_view,
    _meld_wait_context_view,
    present_accepted_meld,
    present_archived_meld,
    present_deferred_meld,
    present_existing_meld,
    present_incomplete_meld,
    present_restarted_meld,
    present_resumed_meld,
    present_started_meld,
)


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _preserve_all_guidance(session: MeldSession) -> str:
    if session.mode == "DIRECTIONAL":
        return (
            "Preserve the BASELINE except where supported INCOMING evidence "
            "explicitly corrects it. Retain supported incoming distinctions "
            "with explicit scope and provenance."
        )
    return (
        "Preserve every remaining supported source distinction with explicit "
        "scope and provenance. Do not present unresolved alternatives as one "
        "consistent rule."
    )


def _issue_selector(
    session: MeldSession,
    selector: str,
) -> MeldIssue:
    assessment = session.current_assessment
    if assessment is None:
        raise MeldCommandError("The meld has no assessed issues.")
    ordered_issues = sorted(
        assessment.issues,
        key=lambda item: 0 if item.priority == "REQUIRED" else 1,
    )
    if selector.isdigit():
        index = int(selector)
        if 1 <= index <= len(ordered_issues):
            return ordered_issues[index - 1]
    matches = [issue for issue in assessment.issues if issue.uid.startswith(selector)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise MeldCommandError(f"No meld issue matches '{selector}'.")
    raise MeldCommandError(f"Meld issue selector '{selector}' is ambiguous.")


def _load_bound_contexts(
    store: MemoryStore,
    session: MeldSession,
    *,
    registry=None,
) -> tuple[Context, Context, Context]:
    if session.schema_version == MELD_INLINE_MEMORY_SCHEMA_VERSION:
        left = inline_meld_context(session)
        baseline = session.frames[1]
        right = load_context_scope(
            store,
            baseline.context_name,
            include_descendants=bool(baseline.include_descendants),
        )
        return left, right, right
    if session.mode == "DIRECTIONAL" and (
        session.granted_incoming is not None or session.granted_target is not None
    ):
        bindings = (session.granted_incoming, session.granted_target)
        loaded = []
        for frame, binding in zip(session.frames, bindings, strict=True):
            if binding is None:
                access = ContextAccess(
                    store=store,
                    context_name=frame.context_name,
                    display_name=frame.context_name,
                    attachment_name=None,
                    permission="READ",
                )
            else:
                access = revalidate_granted_context_binding(
                    binding,
                    registry=registry,
                )
            loaded.append(
                _load_meld_source(
                    access,
                    include_descendants=bool(frame.include_descendants),
                    project=(session.schema_version < MELD_OWNER_AWARE_SCHEMA_VERSION),
                )
            )
        left, right = loaded
        # Directional BASELINE is the target. Loading it through the frozen
        # endpoint preserves its public identity while reading authority data.
        return left, right, right
    try:
        loaded: list[Context] = []
        for frame in session.frames:
            if (
                session.mode == "DIRECTIONAL"
                and session.schema_version >= MELD_OWNER_AWARE_SCHEMA_VERSION
            ):
                context = load_context_scope(
                    store,
                    frame.context_name,
                    include_descendants=bool(frame.include_descendants),
                )
            else:
                context = (
                    recursive_comparison_projection(
                        load_context_scope(
                            store,
                            frame.context_name,
                            include_descendants=bool(frame.include_descendants),
                        )
                    )
                    if frame.include_descendants
                    else store.load_direct(frame.context_name)
                )
            loaded.append(context)
        left, right = loaded
    except FileNotFoundError:
        if session.mode != "SYMMETRIC" or session.comparison_seed is None:
            raise
        artifact = load_granted_comparison_artifact(
            store,
            session.frames[0].context_uid,
            session.frames[1].context_uid,
        )
        if artifact is None:
            raise MeldCommandError(
                "The granted Compare basis for this Meld is unavailable."
            )
        left, right = granted_artifact_contexts(store, artifact)
    target = (
        right
        if session.mode == "DIRECTIONAL"
        and session.schema_version >= MELD_OWNER_AWARE_SCHEMA_VERSION
        else store.load_direct(session.target.context_name)
    )
    return left, right, target


def _resolve_meld_source(
    store: MemoryStore,
    name: str,
    *,
    current_name: str | None,
) -> ContextAccess:
    return resolve_context_access(
        store,
        name,
        current_name=current_name,
        required_permission="READ",
    )


def _load_meld_source(
    access: ContextAccess,
    *,
    include_descendants: bool = False,
    project: bool = True,
) -> Context:
    if include_descendants:
        reader = GrantedReadStore(access) if access.is_granted else access.store
        context = load_context_scope(
            reader,
            access.display_name if access.is_granted else access.context_name,
            include_descendants=True,
        )
    else:
        context = (
            (
                GrantedReadStore(access).load(access.display_name)
                if project
                else GrantedReadStore(access).load_direct(access.display_name)
            )
            if access.is_granted
            else access.store.load_direct(access.context_name)
        )
    return recursive_comparison_projection(context) if project else context


def _load_local_meld_source(
    store: MemoryStore,
    name: str,
    *,
    include_descendants: bool,
    project: bool = True,
) -> Context:
    if not include_descendants:
        return store.load_direct(name)
    context = load_context_scope(
        store,
        name,
        include_descendants=True,
    )
    return recursive_comparison_projection(context) if project else context


def _meld_request_matches_saved_session(
    session: MeldSession,
    *,
    requested_mode: str,
    left_name: str,
    right_name: str,
    left_descendants: bool,
    right_descendants: bool,
    incoming_text: str | None,
    incoming_memory: str | None,
    baseline_memory: str | None,
) -> bool:
    """Compare one explicit start frame with the target's current work slot."""

    if session.mode != requested_mode:
        return False
    saved_names = tuple(frame.context_name for frame in session.frames)
    sources_match = (
        saved_names == (left_name, right_name)
        if requested_mode == "DIRECTIONAL"
        else set(saved_names) == {left_name, right_name}
    )
    sources_match = sources_match and tuple(
        bool(frame.include_descendants) for frame in session.frames
    ) == (left_descendants, right_descendants)
    sources_match = sources_match and (
        (
            session.schema_version == MELD_INLINE_MEMORY_SCHEMA_VERSION
            and len(session.frames[0].memories) == 1
            and session.frames[0].memories[0].content == incoming_text
        )
        if incoming_text is not None
        else session.schema_version != MELD_INLINE_MEMORY_SCHEMA_VERSION
    )
    for selector, frame, label in (
        (incoming_memory, session.frames[0], "INCOMING Memory"),
        (baseline_memory, session.frames[1], "BASELINE Memory"),
    ):
        requested_uid = None
        if selector is not None:
            try:
                focus = resolve_memory_focus(
                    (*frame.memories, *frame.context_evidence),
                    selector,
                    label=label,
                )
            except MemoryFocusError as error:
                raise MeldCommandError(str(error)) from error
            requested_uid = focus.selected_uid
        sources_match = sources_match and frame.selected_memory_uid == requested_uid
    return sources_match


def _bound_frame_digest(frame, context: Context) -> str:
    if frame.contexts is None:
        return context_record_digest(context)
    return MeldFrame.from_context(
        context,
        role=frame.role,
        include_descendants=frame.include_descendants,
        owner_aware=True,
    ).context_digest


def _assert_source_bindings(
    session: MeldSession,
    left: Context,
    right: Context,
) -> None:
    for frame, context in zip(
        session.frames,
        (left, right),
        strict=True,
    ):
        if (
            context.uid != frame.context_uid
            or context.name != frame.context_name
            or _bound_frame_digest(frame, context) != frame.context_digest
        ):
            raise MeldCommandError(
                f"Source Context '{frame.context_name}' changed after this "
                "meld was analyzed."
            )


def _assert_non_target_source_bindings(
    session: MeldSession,
    left: Context,
    right: Context,
) -> None:
    """Recheck read-only inputs while allowing an applied baseline to differ."""
    for frame, context in zip(
        session.frames,
        (left, right),
        strict=True,
    ):
        if (
            frame.context_uid == session.target.context_uid
            and frame.context_name == session.target.context_name
        ):
            continue
        if (
            context.uid != frame.context_uid
            or context.name != frame.context_name
            or _bound_frame_digest(frame, context) != frame.context_digest
        ):
            raise MeldCommandError(
                f"Source Context '{frame.context_name}' changed after this "
                "meld was analyzed."
            )


def _assert_unapplied_target(
    session: MeldSession,
    target: Context,
) -> None:
    target_digest = (
        _bound_frame_digest(session.frames[1], target)
        if session.mode == "DIRECTIONAL"
        else context_record_digest(target)
    )
    if (
        target.uid != session.target.context_uid
        or target.name != session.target.context_name
        or target_digest != session.target.context_digest
    ):
        raise MeldCommandError(
            "The meld target changed after analysis; the proposal is stale."
        )


def _assess_and_save(
    *,
    store: MemoryStore,
    session: MeldSession,
    provider_factory,
    expected_session_digest: str | None,
) -> MeldSession:
    from memcommit.application.operations.meld.runtime import (
        execute_prepared_meld_turn,
        prepare_pending_meld_turn,
    )
    from memcommit.application.operations.meld.sessions import (
        PendingMeldTurn,
    )

    prepared = prepare_pending_meld_turn(
        PendingMeldTurn(
            session=session,
            expected_version=expected_session_digest,
        ),
        store=store,
    )

    def connected_provider():
        return provider_factory()

    if not prepared.provider_required:
        return execute_prepared_meld_turn(
            prepared,
            provider_factory=lambda: (_ for _ in ()).throw(
                AssertionError("A cached Meld assessment connected a provider.")
            ),
        ).session

    def assess(progress):
        def observe(stage: str) -> None:
            if stage == "ANALYZING":
                progress.update("analyzing meld turn", step=2)
            elif stage == "REPAIRING":
                progress.update("repairing invalid meld turn", step=2)

        return execute_prepared_meld_turn(
            prepared,
            provider_factory=connected_provider,
            observer=observe,
        ).session

    if len(session.turns) > 1:
        return run_command_wait(
            "MELD",
            "connecting provider",
            total=2,
            work=assess,
            return_view=_meld_wait_view(session),
            context_view=_meld_wait_context_view(session),
        )
    return run_command_wait(
        "MELD",
        "connecting provider",
        total=2,
        work=assess,
    )


def _accept(
    *,
    store: MemoryStore,
    session: MeldSession,
    expected_session_digest: str,
) -> tuple[bool, str, int]:
    """Hand one explicitly accepted Meld to the operation-owned Apply service."""

    from memcommit.application.operations.meld.apply import MeldApplyRequest
    from memcommit.application.operations.meld.runtime import execute_meld_apply

    receipt = execute_meld_apply(
        MeldApplyRequest(
            session=session,
            expected_session_digest=expected_session_digest,
        ),
        store=store,
    ).receipt
    return receipt.recovered, receipt.checkpoint_uid, receipt.result_count


def _complete_default_terminal_execution(
    *,
    store: MemoryStore,
    session: MeldSession,
) -> MeldSession:
    """Finish a normal terminal Meld without opening a response turn.

    Symmetric Compare already supplies an exhaustive relation ledger.  Meld
    materializes that ledger conservatively in the same initial turn, then
    applies any decision-complete local result.  Granted-target writes retain
    their explicit authority approval boundary, and unresolved directional
    analyses remain terminal incomplete receipts rather than conversations.
    """

    if not _interactive_terminal():
        return session
    if session.mode == "SYMMETRIC" and session.state == "AWAITING_REPLY":
        from memcommit.application.operations.meld.runtime import (
            execute_meld_initial_preservation,
        )
        from memcommit.application.operations.meld.sessions import (
            MeldSessionSnapshot,
        )

        expected = meld_canonical_digest(session.to_dict())
        session = execute_meld_initial_preservation(
            MeldSessionSnapshot(session=session, version_token=expected),
            store=store,
        ).session
    if session.state == "READY_TO_APPLY" and session.granted_target is None:
        _accept(
            store=store,
            session=session,
            expected_session_digest=meld_canonical_digest(session.to_dict()),
        )
        applied = store.load_meld_session(session.target.context_uid)
        if applied is None or applied.state != "APPLIED":
            raise MeldCommandError(
                "Meld Apply completed without a reloadable applied receipt."
            )
        session = applied
    return session


def _run_interactive(
    *,
    store: MemoryStore,
    session: MeldSession,
    provider_factory,
    allow_apply: bool = True,
    analysis_origin: str | None = None,
) -> MeldSession:
    """Run issue and whole-set turns through one shared interactive shell."""
    from memcommit.adapters.console.terminal.components.resolution.session_shell import (
        ResolutionDestination,
    )
    from memcommit.application.operations.meld.runtime import (
        execute_meld_destination_change,
        execute_meld_preservation,
        execute_meld_session_defer,
    )
    from memcommit.application.operations.meld.sessions import (
        MeldDestinationRequest,
        MeldSessionSnapshot,
        prepare_meld_preservation_turn,
    )
    from memcommit.application.operations.meld.resolution import (
        MeldResolutionTurnRequest,
        prepare_meld_resolution_turn,
    )

    if analysis_origin is None and session.comparison_seed is not None:
        from memcommit.study_scenarios.legacy.prewarm.compare import (
            installed_compare_prewarm_origin,
        )

        analysis_origin = installed_compare_prewarm_origin(
            store,
            session.comparison_seed.analysis,
        )
    navigation = ResolutionNavigation()
    while session.state not in {"APPLIED", "KEPT_REVIEW_ONLY"}:

        def validate_destination(name: str) -> None:
            validate_portable_context_name(name)
            if name == session.target.context_name:
                return
            descendants = tuple(
                candidate
                for candidate in store.list_context_names()
                if candidate.startswith(session.target.context_name + "/")
            )
            if descendants:
                raise ValueError(
                    "A symmetric Meld save location with descendants cannot "
                    "be moved from the review workbench."
                )
            store.plan_context_rename(session.target.context_name, name)

        destination = (
            ResolutionDestination(
                value=session.target.context_name,
                state="CURRENT TARGET",
                validate=validate_destination,
                context_names=tuple(store.list_context_names()),
                current_context=store.current_context_name(),
            )
            if allow_apply and session.mode == "SYMMETRIC"
            else None
        )
        # Each visible option is a provider-free local branch. Persist only
        # its exact issue/option selection (and optional explanation) while
        # the person reviews; the provider sees the choices together only
        # after the workbench builds one explicit whole-ledger action.
        choice_branches = (
            store.load_meld_choice_branches(session)
            if session.current_assessment is not None
            else None
        )

        def load_choice(issue_uid: str) -> tuple[str | None, str]:
            assert choice_branches is not None
            return choice_branches.response_for(issue_uid)

        def save_choice(
            issue_uid: str,
            option_uid: str | None,
            explanation: str,
        ) -> None:
            nonlocal choice_branches
            assert choice_branches is not None
            choice_branches = choice_branches.with_response(
                session,
                issue_uid=issue_uid,
                option_uid=option_uid,
                explanation=explanation,
            )
            store.save_meld_choice_branches(session, choice_branches)

        action = run_meld_shell(
            session,
            navigation=navigation,
            review_only=not allow_apply,
            destination=destination,
            analysis_origin=analysis_origin,
            draft_loader=(load_choice if choice_branches is not None else None),
            draft_saver=(save_choice if choice_branches is not None else None),
        )
        if action is None:
            break
        expected = meld_canonical_digest(session.to_dict())
        snapshot = MeldSessionSnapshot(session=session, version_token=expected)
        if action.kind == "CHANGE_DESTINATION":
            if destination is None or action.destination is None:
                raise MeldCommandError("This Meld cannot change its save location.")
            validate_destination(action.destination)
            if action.destination != session.target.context_name:
                session = execute_meld_destination_change(
                    MeldDestinationRequest(
                        snapshot=snapshot,
                        destination_name=action.destination,
                    ),
                    store=store,
                ).session
            continue
        if action.kind == "DEFER_ALL":
            session = execute_meld_session_defer(snapshot, store=store).session
            break
        if action.kind == "ACCEPT":
            if not allow_apply:
                raise MeldCommandError("Review cannot apply a Meld target.")
            _accept(
                store=store,
                session=session,
                expected_session_digest=expected,
            )
            break
        if action.kind == "PRESERVE_ALL":
            pending = prepare_meld_preservation_turn(
                snapshot,
                guidance=_preserve_all_guidance(session),
            )
            session = pending.session
            if (
                session.mode == "SYMMETRIC"
                and session.schema_version >= MELD_SCHEMA_VERSION
            ):
                session = execute_meld_preservation(pending, store=store).session
                continue
        elif action.kind == "COMMENT_ALL":
            session = prepare_meld_resolution_turn(
                MeldResolutionTurnRequest(
                    snapshot=snapshot,
                    comment=action.comment,
                )
            ).session
        elif action.kind == "COMMENT_ISSUE":
            assert action.issue_uid is not None
            session = prepare_meld_resolution_turn(
                MeldResolutionTurnRequest(
                    snapshot=snapshot,
                    issue_uid=action.issue_uid,
                    option_uid=action.option_uid,
                    comment=action.comment,
                )
            ).session
        else:
            raise MeldCommandError(
                f"Unsupported interactive meld action '{action.kind}'."
            )
        session = _assess_and_save(
            store=store,
            session=session,
            provider_factory=provider_factory,
            expected_session_digest=expected,
        )
    return session


def run_meld_review(
    *,
    store: MemoryStore,
    session: MeldSession,
    provider_factory,
) -> MeldSession:
    """Run semantic Meld review turns without exposing target application."""
    return _run_interactive(
        store=store,
        session=session,
        provider_factory=provider_factory,
        allow_apply=False,
    )


def _resume_picked_meld(
    *,
    store: MemoryStore,
    entry: MeldSessionCatalogEntry,
) -> None:
    """Reload, rebind, and open one picker selection without creating state."""
    session = reload_selected_meld_session(store, entry)
    if entry.archived:
        present_archived_meld(session)
        return
    left_ctx, right_ctx, target = _load_bound_contexts(store, session)
    if (
        target.uid != session.target.context_uid
        or target.name != session.target.context_name
    ):
        raise MeldCommandError(
            "The selected Meld target identity no longer matches its saved session."
        )
    _assert_non_target_source_bindings(session, left_ctx, right_ctx)
    if session.state != "APPLIED":
        _assert_source_bindings(session, left_ctx, right_ctx)
        _assert_unapplied_target(session, target)

    interactive_ran = _interactive_terminal()
    terminal_session = session.state in {
        "APPLIED",
        "KEPT_REVIEW_ONLY",
    }
    show_deferred_resume = interactive_ran and session.state == "KEPT_REVIEW_ONLY"
    if interactive_ran and not terminal_session:
        session = _complete_default_terminal_execution(
            store=store,
            session=session,
        )
        if session.state == "APPLIED":
            terminal_session = True
    present_resumed_meld(
        session,
        interactive_ran=interactive_ran,
        terminal_session=terminal_session,
        show_deferred_resume=show_deferred_resume,
    )


def execute_meld_command(
    *,
    store: MemoryStore,
    request: InterpretedMeldCommand,
) -> None:
    """Dispatch one interpreted Meld command against current saved state."""
    requested_mode = request.mode
    left_name = request.left_name
    right_name = request.right_name
    target_name = request.target_name
    current_name = request.current_name
    start_command = request.start_command
    left_descendants = request.left_descendants
    right_descendants = request.right_descendants
    incoming_text = request.incoming_text
    incoming_memory = request.incoming_memory
    baseline_memory = request.baseline_memory
    action = request.action
    issue = request.issue
    choice = request.choice
    comment = request.comment
    expect_session = request.expect_session
    revision = request.revision
    revises_turn = request.revises_turn
    expand = request.expand
    create_target = False
    left_access: ContextAccess | None = None
    right_access: ContextAccess | None = None
    if requested_mode == "DIRECTIONAL":
        right_access = _resolve_meld_source(
            store,
            right_name,
            current_name=current_name,
        )
        if incoming_text is not None:
            if right_access.is_granted:
                raise MeldCommandError(
                    "Inline-Memory Meld currently requires a local BASELINE/Target."
                )
        else:
            left_access = _resolve_meld_source(
                store,
                left_name,
                current_name=current_name,
            )
            authorize_combination((left_access, right_access))
            authorize_derived_transfer(left_access, right_access)
            retention = analysis_retention((left_access, right_access))
            if retention is None:
                raise ProfileError(
                    "The directional Meld cannot save analysis under the "
                    "available Grants."
                )
            authorize_analysis_save(
                (left_access, right_access),
                retention=retention,
            )

    if requested_mode == "SYMMETRIC" and not store.context_exists(target_name):
        create_target = True
    if create_target:
        # The runtime allocates and publishes the real Context atomically
        # with its session. This placeholder carries only the reviewed name
        # through the CLI's provider-free Compare prerequisite flow.
        target = Context(uid="", name=target_name)
        session = None
    else:
        target = (
            _load_meld_source(right_access)
            if requested_mode == "DIRECTIONAL" and right_access is not None
            else store.load_direct(target_name)
        )
        session = store.load_meld_session(target.uid)
    if requested_mode == "SYMMETRIC" and session is None:
        left_access = _resolve_meld_source(
            store,
            left_name,
            current_name=current_name,
        )
        right_access = _resolve_meld_source(
            store,
            right_name,
            current_name=current_name,
        )
        target_access = (
            ContextAccess(
                store=store,
                context_name=target_name,
                display_name=target_name,
                attachment_name=None,
                permission="READ",
            )
            if create_target
            else resolve_context_access(
                store,
                target_name,
                current_name=current_name,
                required_permission="READ",
            )
        )
        if target_access.is_granted:
            raise MeldCommandError(
                "Symmetric granted-source Meld currently requires a local "
                "participant target."
            )
        authorize_combination((left_access, right_access))
        authorize_derived_transfer(left_access, target_access)
        authorize_derived_transfer(right_access, target_access)
    request_matches_saved = session is not None and _meld_request_matches_saved_session(
        session,
        requested_mode=requested_mode,
        left_name=left_name,
        right_name=right_name,
        left_descendants=left_descendants,
        right_descendants=right_descendants,
        incoming_text=incoming_text,
        incoming_memory=incoming_memory,
        baseline_memory=baseline_memory,
    )
    auto_restart = bool(
        session is not None
        and session.state in {"APPLIED", "KEPT_REVIEW_ONLY"}
        and not request_matches_saved
        and action == "NONE"
        and expand is None
    )
    if session is None:
        if action != "NONE":
            raise MeldCommandError(
                f"Start the meld with a plain '{start_command}' first."
            )
        request = MeldStartRequest(
            mode=requested_mode,
            left_name=left_name,
            right_name=right_name,
            target_name=target_name,
            left_descendants=left_descendants,
            right_descendants=right_descendants,
            create_target=create_target,
            incoming_memory=incoming_memory,
            baseline_memory=baseline_memory,
            incoming_text=incoming_text,
        )
        from memcommit.application.operations.meld.runtime import (
            execute_meld_start,
            prepare_meld_start,
        )

        prepared = prepare_meld_start(request, store=store)
        directional_prewarm_origin = (
            prepared.directional_prewarm.origin
            if prepared.directional_prewarm is not None
            else None
        )
        if prepared.provider_required:

            def start_meld(progress):
                def connected_provider():
                    provider = connect_codex_chatgpt_provider()
                    progress.update("analyzing meld turn", step=2)
                    return provider

                return execute_meld_start(
                    request,
                    store=store,
                    provider_factory=connected_provider,
                    prepared=prepared,
                )

            stage = (
                "connecting provider"
                if requested_mode == "DIRECTIONAL"
                else "preparing ordered Compare basis"
            )
            started = run_command_wait(
                "MELD",
                stage,
                total=2,
                work=start_meld,
            )
        else:
            started = execute_meld_start(
                request,
                store=store,
                provider_factory=lambda: (_ for _ in ()).throw(
                    AssertionError("A prepared Meld start connected a provider.")
                ),
                prepared=prepared,
            )
        session = started.session
        if requested_mode == "DIRECTIONAL":
            directional_prewarm_origin = (
                started.origin if started.origin != "PROVIDER" else None
            )
        session = _complete_default_terminal_execution(
            store=store,
            session=session,
        )
        present_started_meld(
            session,
            directional_prewarm_origin=(
                directional_prewarm_origin if requested_mode == "DIRECTIONAL" else None
            ),
        )
        return

    if action == "RESTART" or auto_restart:
        prior_session_uid = session.uid
        prior_digest = meld_canonical_digest(session.to_dict())
        restart_request = MeldRestartRequest(
            mode=requested_mode,
            left_name=left_name,
            right_name=right_name,
            target_name=target_name,
            expected_version=prior_digest,
            left_descendants=left_descendants,
            right_descendants=right_descendants,
            incoming_memory=incoming_memory,
            baseline_memory=baseline_memory,
            incoming_text=incoming_text,
        )
        from memcommit.application.operations.meld.runtime import (
            execute_meld_restart,
            prepare_meld_restart,
        )

        prepared = prepare_meld_restart(restart_request, store=store)
        if prepared.provider_required:

            def restart_meld(progress):
                def connected_provider():
                    provider = connect_codex_chatgpt_provider()
                    progress.update("analyzing meld turn", step=2)
                    return provider

                return execute_meld_restart(
                    restart_request,
                    store=store,
                    provider_factory=connected_provider,
                    prepared=prepared,
                )

            stage = (
                "connecting provider"
                if requested_mode == "DIRECTIONAL"
                else "preparing ordered Compare basis"
            )
            restarted = run_command_wait(
                "MELD",
                stage,
                total=2,
                work=restart_meld,
            )
        else:
            restarted = execute_meld_restart(
                restart_request,
                store=store,
                provider_factory=lambda: (_ for _ in ()).throw(
                    AssertionError("A prepared Meld restart connected a provider.")
                ),
                prepared=prepared,
            )
        session = restarted.session
        session = _complete_default_terminal_execution(
            store=store,
            session=session,
        )
        present_restarted_meld(
            session,
            prior_session_uid=prior_session_uid if auto_restart else None,
        )
        return

    if session.mode != requested_mode:
        raise MeldCommandError(
            "The target already has a saved meld with a different "
            "authority mode. Use --restart to replace it."
        )
    if not request_matches_saved:
        raise MeldCommandError(
            "The target already has a meld from different sources. Use "
            "--restart to replace it."
        )
    expected_session_digest = meld_canonical_digest(session.to_dict())
    if expect_session is not None and expect_session != expected_session_digest:
        raise MeldCommandError(
            "The saved Meld session changed after this command was reviewed. "
            "Reopen it and rebuild the turn command."
        )
    from memcommit.application.operations.meld.runtime import (
        execute_meld_preservation,
        execute_meld_session_defer,
    )
    from memcommit.application.operations.meld.sessions import (
        MeldSessionSnapshot,
        prepare_meld_preservation_turn,
    )
    from memcommit.application.operations.meld.resolution import (
        MeldResolutionTurnRequest,
        prepare_meld_resolution_turn,
    )

    session_snapshot = MeldSessionSnapshot(
        session=session,
        version_token=expected_session_digest,
    )
    left_ctx, right_ctx, target = _load_bound_contexts(store, session)
    _assert_non_target_source_bindings(session, left_ctx, right_ctx)
    if session.state != "APPLIED" and action != "ACCEPT":
        _assert_source_bindings(session, left_ctx, right_ctx)
        _assert_unapplied_target(session, target)

    if action == "ACCEPT":
        recovered, _checkpoint_uid, _result_count = _accept(
            store=store,
            session=session,
            expected_session_digest=expected_session_digest,
        )
        present_accepted_meld(session, recovered=recovered)
        return

    if action == "DEFER_ALL":
        session = execute_meld_session_defer(
            session_snapshot,
            store=store,
        ).session
        present_deferred_meld(session)
        return

    if action == "PRESERVE_ALL":
        pending = prepare_meld_preservation_turn(
            session_snapshot,
            guidance=_preserve_all_guidance(session),
        )
        session = pending.session
        if (
            session.mode == "SYMMETRIC"
            and session.schema_version >= MELD_SCHEMA_VERSION
        ):
            session = execute_meld_preservation(pending, store=store).session
        else:
            session = _assess_and_save(
                store=store,
                session=session,
                provider_factory=connect_codex_chatgpt_provider,
                expected_session_digest=expected_session_digest,
            )
        present_incomplete_meld(session)
        return

    if action == "RESPONSE":
        selected_issue = _issue_selector(session, issue) if issue is not None else None
        option_uid = None
        if choice is not None:
            assert selected_issue is not None
            if choice > len(selected_issue.options):
                raise MeldCommandError(
                    f"Issue has only {len(selected_issue.options)} choices."
                )
            option_uid = selected_issue.options[choice - 1].uid
        revision_value = (revision or "extend").strip().upper()
        if revision_value not in {
            "CONFIRM",
            "EXTEND",
            "CORRECT",
            "RETRACT",
        }:
            raise MeldCommandError(
                "--revision must be confirm, extend, correct, or retract."
            )
        revises = tuple(revises_turn or ())
        if revises and revision_value not in {"CORRECT", "RETRACT"}:
            raise MeldCommandError(
                "--revises-turn is valid only with --revision correct or retract."
            )
        session = prepare_meld_resolution_turn(
            MeldResolutionTurnRequest(
                snapshot=session_snapshot,
                comment=comment or "",
                issue_uid=(selected_issue.uid if selected_issue is not None else None),
                option_uid=option_uid,
                revision=revision_value,  # type: ignore[arg-type]
                revises_turn_uids=revises,
            )
        ).session
        session = _assess_and_save(
            store=store,
            session=session,
            provider_factory=connect_codex_chatgpt_provider,
            expected_session_digest=expected_session_digest,
        )
        present_incomplete_meld(session)
        return

    expanded_uid = None
    if expand is not None:
        expanded_uid = _issue_selector(session, expand).uid
    interactive_ran = (
        expand is None
        and _interactive_terminal()
        and session.state not in {"APPLIED", "KEPT_REVIEW_ONLY"}
    )
    if interactive_ran:
        session = _complete_default_terminal_execution(
            store=store,
            session=session,
        )
    present_existing_meld(
        session,
        expanded_issue_uid=expanded_uid,
        interactive_ran=interactive_ran,
    )
