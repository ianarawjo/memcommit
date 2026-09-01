"""Console workflow orchestration for Meld application services."""

from __future__ import annotations

import sys

from memcommit.core.context import Context, Memory
from memcommit.application.capabilities.context_scope_loading import load_context_scope
from memcommit.application.capabilities.semantic.memory_scope import (
    MemoryScopeError,
    resolve_memory_scope,
)
from memcommit.application.context_access.access import (
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
    load_granted_memory_relation_artifact,
    project_memory_relation_context,
)
from memcommit.application.operations.meld.model import (
    MELD_CANDIDATE_SCHEMA_VERSION,
    MELD_INLINE_MEMORY_SCHEMA_VERSION,
    MELD_OWNER_AWARE_SCHEMA_VERSION,
    MeldFrame,
    MeldSession,
    inline_meld_context,
    meld_canonical_digest,
)
from memcommit.adapters.console.commands.resolve.workbench.screen import (
    run_resolve_tui,
)
from memcommit.application.operations.meld.preparation import MeldRestartRequest
from memcommit.application.operations.meld.preparation import MeldStartRequest
from memcommit.adapters.console.commands.meld.sessions import (
    MeldSessionCatalogEntry,
    reload_selected_meld_session,
)
from memcommit.providers.subscription import (
    connect_codex_chatgpt_provider,
)
from memcommit.persistence.store import (
    MemoryStore,
    context_record_digest,
)

from memcommit.adapters.console.commands.meld.errors import MeldCommandError
from memcommit.adapters.console.commands.meld.interpretation import (
    InterpretedMeldCommand,
)
from memcommit.adapters.console.commands.meld.presentation import (
    present_archived_meld,
    present_existing_meld,
    present_restarted_meld,
    present_resumed_meld,
    present_started_meld,
)


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _load_bound_contexts(
    store: MemoryStore,
    session: MeldSession,
    *,
    registry=None,
) -> tuple[Context, Context, Context]:
    if session.schema_version == MELD_INLINE_MEMORY_SCHEMA_VERSION or (
        session.schema_version == MELD_CANDIDATE_SCHEMA_VERSION
        and session.frames[0].context_name == "INLINE MEMORY"
    ):
        if session.schema_version == MELD_INLINE_MEMORY_SCHEMA_VERSION:
            left = inline_meld_context(session)
        else:
            frame = session.frames[0]
            left = Context(uid=frame.context_uid, name=frame.context_name)
            for source_memory in frame.memories:
                left.add(Memory(source_memory.uid, source_memory.content))
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
                    access_name=frame.context_name,
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
                    project_memory_relation_context(
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
        if session.mode != "SYMMETRIC" or session.relation_analysis_seed is None:
            raise
        artifact = load_granted_memory_relation_artifact(
            store,
            session.frames[0].context_uid,
            session.frames[1].context_uid,
        )
        if artifact is None:
            raise MeldCommandError(
                "The granted relation-analysis basis for this Meld is unavailable."
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
            access.access_name if access.is_granted else access.context_name,
            include_descendants=True,
        )
    else:
        context = (
            (
                GrantedReadStore(access).load(access.access_name)
                if project
                else GrantedReadStore(access).load_direct(access.access_name)
            )
            if access.is_granted
            else access.store.load_direct(access.context_name)
        )
    return project_memory_relation_context(context) if project else context


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
    return project_memory_relation_context(context) if project else context


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
    """Analyze one explicit start frame against the target's current work slot."""

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
                scope = resolve_memory_scope(
                    (*frame.memories, *frame.context_evidence),
                    selector,
                    label=label,
                )
            except MemoryScopeError as error:
                raise MeldCommandError(str(error)) from error
            requested_uid = scope.selected_uid
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


def _complete_default_terminal_execution(
    *,
    store: MemoryStore,
    session: MeldSession,
    provider_factory=connect_codex_chatgpt_provider,
) -> MeldSession:
    """Finish a candidate Meld, while keeping legacy sessions read-only."""

    if session.schema_version == MELD_CANDIDATE_SCHEMA_VERSION:
        review = session.candidate_review
        if not _interactive_terminal() and (review is None or review.issues):
            return session
        return _run_candidate_interactive(
            store=store,
            session=session,
            provider_factory=provider_factory,
        )
    # Compare-backed sessions remain inspectable, but may never re-enter their
    # former proposal/apply path. Restart is the explicit migration boundary.
    return session


def _run_candidate_interactive(
    *,
    store: MemoryStore,
    session: MeldSession,
    provider_factory,
) -> MeldSession:
    """Collect Resolve decisions and execute one verified whole-candidate Update."""

    from memcommit.application.operations.meld.resolution import (
        plan_meld_candidate_update,
    )
    from memcommit.application.operations.meld.runtime import (
        execute_meld_candidate_proposal,
    )

    while session.state not in {"APPLIED", "KEPT_REVIEW_ONLY"}:
        review = session.candidate_review
        if review is None:
            raise MeldCommandError("The Meld candidate review is unavailable.")
        analysis = review.resolve_analysis()
        if analysis.review_issues:
            decisions = run_resolve_tui(analysis, header_label="MELD")
            if decisions is None:
                return session
        else:
            decisions = ()
        expected = meld_canonical_digest(session.to_dict())
        target = store.load_direct(session.target.context_name)

        def plan_and_verify(progress):
            calls = {"value": 0}

            def connect(stage: str):
                calls["value"] += 1
                progress.update(stage, step=min(calls["value"], 3))
                return provider_factory()

            return plan_meld_candidate_update(
                session,
                decisions,
                target=target,
                update_provider_factory=lambda: connect("planning candidate Update"),
                audit_provider_factory=lambda: connect("auditing complete post-image"),
                direction_provider_factory=lambda: connect("deriving next directions"),
                coverage_provider_factory=lambda: connect("checking Source coverage"),
            )

        proposal = run_command_wait(
            "MELD",
            "building whole-candidate Update",
            total=3,
            work=plan_and_verify,
        )
        session, receipt = execute_meld_candidate_proposal(
            session,
            proposal,
            store=store,
            expected_session_digest=expected,
        )
        if receipt.missing_claim_aliases:
            raise MeldCommandError(
                "The proposed Meld post-image dropped Source claim(s): "
                + ", ".join(receipt.missing_claim_aliases)
                + ". Nothing was applied."
            )
        if receipt.applied:
            applied = store.load_meld_session(session.target.context_uid)
            if applied is None or applied.state != "APPLIED":
                raise MeldCommandError(
                    "Meld Apply completed without a reloadable receipt."
                )
            return applied
        # A new post-image conflict or ambiguity becomes the next Resolve turn.
        if not _interactive_terminal():
            return session
    return session


def _run_interactive(
    *,
    store: MemoryStore,
    session: MeldSession,
    provider_factory,
    allow_apply: bool = True,
    analysis_origin: str | None = None,
) -> MeldSession:
    """Run candidate decisions; legacy Compare-backed sessions are read-only."""
    if session.schema_version == MELD_CANDIDATE_SCHEMA_VERSION:
        if not allow_apply:
            return session
        return _run_candidate_interactive(
            store=store,
            session=session,
            provider_factory=provider_factory,
        )
    # Keeping this function as the public review adapter preserves historical
    # sessions as evidence without preserving their executable Compare path.
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
            provider_factory=connect_codex_chatgpt_provider,
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
    expect_session = request.expect_session
    expand = request.expand
    create_target = False
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
            _resolve_meld_source(
                store,
                left_name,
                current_name=current_name,
            )

    if requested_mode == "SYMMETRIC" and not store.context_exists(target_name):
        create_target = True
    if create_target:
        # The runtime allocates and publishes the real Context atomically
        # with its session. This placeholder carries only the reviewed name
        # through the CLI's provider-free preparation boundary.
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
        _resolve_meld_source(
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
                access_name=target_name,
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
        if prepared.provider_required:

            def start_meld(progress):
                def connected_provider():
                    provider = connect_codex_chatgpt_provider()
                    progress.update("auditing lossless candidate", step=2)
                    return provider

                return execute_meld_start(
                    request,
                    store=store,
                    provider_factory=connected_provider,
                    prepared=prepared,
                )

            started = run_command_wait(
                "MELD",
                "building and auditing lossless candidate",
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
        session = _complete_default_terminal_execution(
            store=store,
            session=session,
            provider_factory=connect_codex_chatgpt_provider,
        )
        present_started_meld(
            session,
            directional_prewarm_origin=None,
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
                    progress.update("auditing lossless candidate", step=2)
                    return provider

                return execute_meld_restart(
                    restart_request,
                    store=store,
                    provider_factory=connected_provider,
                    prepared=prepared,
                )

            restarted = run_command_wait(
                "MELD",
                "building and auditing lossless candidate",
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
            provider_factory=connect_codex_chatgpt_provider,
        )
        present_restarted_meld(
            session,
            prior_session_uid=prior_session_uid if auto_restart else None,
        )
        return

    if session.schema_version != MELD_CANDIDATE_SCHEMA_VERSION:
        if action != "NONE" or expand is not None:
            raise MeldCommandError(
                "This Compare-backed Meld session is retained as read-only history. "
                "Use --restart to rebuild it through Audit, Resolve, and Update."
            )
        present_existing_meld(
            session,
            expanded_issue_uid=None,
            interactive_ran=False,
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
    if action != "NONE" or expand is not None:
        raise MeldCommandError(
            "Candidate Meld decisions are finalized together in the interactive "
            "Resolve view; legacy --choice/--comment/--accept actions are unavailable."
        )
    left_ctx, right_ctx, target = _load_bound_contexts(store, session)
    _assert_non_target_source_bindings(session, left_ctx, right_ctx)
    if session.state != "APPLIED":
        _assert_source_bindings(session, left_ctx, right_ctx)
        _assert_unapplied_target(session, target)

    expanded_uid = None
    interactive_ran = (
        _interactive_terminal()
        and session.state not in {"APPLIED", "KEPT_REVIEW_ONLY"}
    )
    if interactive_ran:
        session = _complete_default_terminal_execution(
            store=store,
            session=session,
            provider_factory=connect_codex_chatgpt_provider,
        )
    present_existing_meld(
        session,
        expanded_issue_uid=expanded_uid,
        interactive_ran=interactive_ran,
    )
