"""Meld Source access, frozen bindings, and target revalidation."""

from __future__ import annotations

from memcommit.application.context_access.access import (
    ContextAccess,
    GrantedReadStore,
)
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.granted_repository import (
    project_memory_relation_context,
)
from memcommit.application.operations.merge.semantic.model import (
    INLINE_MELD_CONTEXT_NAME,
    MeldError,
    MeldFrame,
    MeldSession,
)
from memcommit.core.context import Context, Memory
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
    store: MemoryStore, session: MeldSession, *, registry=None
) -> tuple[Context, Context, Context]:
    """Reload the exact direct local inputs; inline evidence has no store path."""
    loaded = []
    for frame in session.frames:
        if frame.context_name == INLINE_MELD_CONTEXT_NAME:
            context = Context(uid=frame.context_uid, name=frame.context_name)
            for memory in frame.memories:
                context.add(Memory(memory.uid, memory.content))
        else:
            context = store.load_direct(frame.context_name)
        loaded.append(context)
    left, right = loaded
    target = (
        right
        if session.mode == "DIRECTIONAL"
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
            raise MeldError(
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
            raise MeldError(
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
        raise MeldError(
            "The meld target changed after analysis; the proposal is stale."
        )


def target_save_source_bindings(
    store: MemoryStore, session: MeldSession
) -> tuple[tuple[str, str, str], ...]:
    """Keep direct source records locked through Target publication."""
    bindings = []
    for frame in session.frames:
        if (
            frame.context_name == INLINE_MELD_CONTEXT_NAME
            or frame.context_uid == session.target.context_uid
        ):
            continue
        context = store.load_direct(frame.context_name)
        if (
            context.uid != frame.context_uid
            or meld_bound_frame_digest(frame, context) != frame.context_digest
        ):
            raise MeldError(
                f"Source Context '{frame.context_name}' changed after analysis."
            )
        # Frame digests may include ownership metadata; store CAS uses physical record bytes.
        bindings.append((context.name, context.uid, context_record_digest(context)))
    return tuple(bindings)
