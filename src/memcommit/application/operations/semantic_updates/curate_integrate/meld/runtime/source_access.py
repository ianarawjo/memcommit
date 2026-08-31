"""Meld Source access, frozen bindings, and target revalidation."""

from __future__ import annotations

from memcommit.application.capabilities.authority.context_access import (
    ContextAccess,
    GrantedReadStore,
    revalidate_granted_context_binding,
)
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.granted_repository import (
    memory_relation_artifact_contexts,
    load_granted_memory_relation_artifact,
    project_memory_relation_context,
)
from memcommit.application.operations.semantic_updates.curate_integrate.meld.apply import (
    MeldApplicationError,
)
from memcommit.application.operations.semantic_updates.curate_integrate.meld.model import (
    MELD_INLINE_MEMORY_SCHEMA_VERSION,
    MELD_OWNER_AWARE_SCHEMA_VERSION,
    MeldFrame,
    MeldSession,
    inline_meld_context,
)
from memcommit.core.context import Context
from memcommit.application.capabilities.context_scope_loading import load_context_scope
from memcommit.persistence.store import (
    MemoryStore,
    context_record_digest,
)


def load_meld_source(
    access: ContextAccess,
    *,
    include_descendants: bool = False,
    project: bool = True,
) -> Context:
    """Load one authorized source with Meld's established projection meaning."""

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
    return project_memory_relation_context(context) if project else context


def load_local_meld_source(
    store: MemoryStore,
    name: str,
    *,
    include_descendants: bool,
    project: bool = True,
) -> Context:
    """Load one local source under the same exact/descendant projection rules."""

    if not include_descendants:
        return store.load_direct(name)
    context = load_context_scope(store, name, include_descendants=True)
    return project_memory_relation_context(context) if project else context


def load_bound_meld_contexts(
    store: MemoryStore,
    session: MeldSession,
    *,
    registry=None,
) -> tuple[Context, Context, Context]:
    """Reload the exact frozen frames and application target for one session."""

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
                load_meld_source(
                    access,
                    include_descendants=bool(frame.include_descendants),
                    project=(session.schema_version < MELD_OWNER_AWARE_SCHEMA_VERSION),
                )
            )
        left, right = loaded
        return left, right, right
    try:
        loaded = []
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
            raise MeldApplicationError(
                "The granted relation-analysis basis for this Meld is unavailable."
            )
        left, right = memory_relation_artifact_contexts(store, artifact)
    target = (
        right
        if session.mode == "DIRECTIONAL"
        and session.schema_version >= MELD_OWNER_AWARE_SCHEMA_VERSION
        else store.load_direct(session.target.context_name)
    )
    return left, right, target


def meld_bound_frame_digest(frame, context: Context) -> str:
    if frame.contexts is None:
        return context_record_digest(context)
    return MeldFrame.from_context(
        context,
        role=frame.role,
        include_descendants=frame.include_descendants,
        owner_aware=True,
    ).context_digest


def assert_meld_source_bindings(
    session: MeldSession,
    left: Context,
    right: Context,
) -> None:
    """Reject any source identity or digest drift since analysis."""

    for frame, context in zip(session.frames, (left, right), strict=True):
        if (
            context.uid != frame.context_uid
            or context.name != frame.context_name
            or meld_bound_frame_digest(frame, context) != frame.context_digest
        ):
            raise MeldApplicationError(
                f"Source Context '{frame.context_name}' changed after this "
                "meld was analyzed."
            )


def assert_meld_non_target_source_bindings(
    session: MeldSession,
    left: Context,
    right: Context,
) -> None:
    """Recheck read-only inputs while allowing an applied baseline to differ."""

    for frame, context in zip(session.frames, (left, right), strict=True):
        if (
            frame.context_uid == session.target.context_uid
            and frame.context_name == session.target.context_name
        ):
            continue
        if (
            context.uid != frame.context_uid
            or context.name != frame.context_name
            or meld_bound_frame_digest(frame, context) != frame.context_digest
        ):
            raise MeldApplicationError(
                f"Source Context '{frame.context_name}' changed after this "
                "meld was analyzed."
            )


def assert_unapplied_meld_target(session: MeldSession, target: Context) -> None:
    target_digest = (
        meld_bound_frame_digest(session.frames[1], target)
        if session.mode == "DIRECTIONAL"
        else context_record_digest(target)
    )
    if (
        target.uid != session.target.context_uid
        or target.name != session.target.context_name
        or target_digest != session.target.context_digest
    ):
        raise MeldApplicationError(
            "The meld target changed after analysis; the proposal is stale."
        )


def walk_meld_target_contexts(root: Context) -> tuple[Context, ...]:
    contexts: list[Context] = []
    seen: set[str] = set()

    def visit(context: Context) -> None:
        if context.uid in seen:
            return
        seen.add(context.uid)
        contexts.append(context)
        for item in context.iter_items():
            if isinstance(item, Context):
                visit(item)

    visit(root)
    return tuple(contexts)


def target_save_source_bindings(
    store: MemoryStore,
    session: MeldSession,
) -> tuple[tuple[str, str, str], ...]:
    """Return live local sources that must stay locked through target CAS."""

    if session.mode == "SYMMETRIC" and session.relation_analysis_seed is not None:
        artifact = load_granted_memory_relation_artifact(
            store,
            session.frames[0].context_uid,
            session.frames[1].context_uid,
        )
        if artifact is not None and artifact.retention == "RETAINED":
            return ()
    bindings: list[tuple[str, str, str]] = []
    for index, frame in enumerate(session.frames):
        if session.schema_version == MELD_INLINE_MEMORY_SCHEMA_VERSION and index == 0:
            # The frozen one-Memory source has no storage path or lock. Its
            # exact bytes are already part of the session CAS and checkpoint.
            continue
        if (
            frame.context_uid == session.target.context_uid
            and frame.context_name == session.target.context_name
        ) or (
            session.mode == "DIRECTIONAL"
            and index == 0
            and session.granted_incoming is not None
        ):
            continue
        if session.mode == "SYMMETRIC" and frame.include_descendants:
            scope = load_context_scope(
                store,
                frame.context_name,
                include_descendants=True,
            )
            projected = project_memory_relation_context(scope)
            if (
                projected.uid != frame.context_uid
                or projected.name != frame.context_name
                or context_record_digest(projected) != frame.context_digest
            ):
                raise MeldApplicationError(
                    f"Source Context '{frame.context_name}' changed after this "
                    "meld was analyzed."
                )
            physical_contexts = tuple(
                store.load_direct(context.name)
                for context in walk_meld_target_contexts(scope)
            )
            bindings.extend(
                (context.name, context.uid, context_record_digest(context))
                for context in physical_contexts
            )
            reloaded_scope = load_context_scope(
                store,
                frame.context_name,
                include_descendants=True,
            )
            if (
                context_record_digest(project_memory_relation_context(reloaded_scope))
                != frame.context_digest
            ):
                raise MeldApplicationError(
                    f"Source Context '{frame.context_name}' changed after this "
                    "meld was analyzed."
                )
            continue
        bindings.append((frame.context_name, frame.context_uid, frame.context_digest))
    return tuple(bindings)
