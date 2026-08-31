"""MemoryStore adapter for frozen deterministic Replace plans."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

from memcommit.core.context import AutoCheckpoint, Context, Memory
from memcommit.core.context_targeting.model import ContextScope
from memcommit.core.context_targeting.resolution import expand_lexical_context_names
from memcommit.application.operations.direct_changes.replace.application import (
    FrozenReplaceContext,
    FrozenReplacePlan,
    FrozenReplaceSource,
    ReplaceApplyResult,
    ReplaceCheckpoint,
    ReplaceError,
    ReplacePort,
    ReplaceRequest,
    ReplaceSourceMemory,
    ReplaceStalePlanError,
    apply_replace,
    plan_replace,
)
from memcommit.persistence.store import (
    ConcurrentContextUpdateError,
    MemoryStore,
    context_record_digest,
)


@dataclass(frozen=True, slots=True)
class _StoreReplaceFrame:
    context: Context
    expected_digest: str


@dataclass(frozen=True, slots=True)
class _StoreReplaceToken:
    owner: object
    operation_uid: str
    frames: tuple[_StoreReplaceFrame, ...]
    context_catalog: tuple[str, ...]


class MemoryStoreReplacePort(ReplacePort):
    """Freeze local direct owners and publish one multi-Context command unit."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store
        self._owner = object()

    def _lexical_names(self, request: ReplaceRequest) -> tuple[str, ...]:
        catalog = tuple(self._store.list_context_names())
        if any(name not in catalog for name in request.target_names):
            raise FileNotFoundError(
                "Replace targets must be ordinary local Contexts in this Store."
            )
        return expand_lexical_context_names(
            ContextScope.create(
                request.target_names,
                include_descendants=request.include_descendants,
            ),
            catalog,
        )

    def _scope_names(self, request: ReplaceRequest) -> tuple[str, ...]:
        initial = self._lexical_names(request)
        if not request.follow_embeds:
            return initial
        names: list[str] = []
        visited_uids: set[str] = set()

        def visit(name: str, expected_uid: str | None = None) -> None:
            if not self._store.context_exists(name):
                return
            context = self._store.load_direct(name)
            if expected_uid is not None and context.uid != expected_uid:
                return
            if context.uid in visited_uids:
                return
            visited_uids.add(context.uid)
            names.append(name)
            for item in context.iter_items():
                if isinstance(item, Context):
                    visit(item.name, item.uid)

        for name in initial:
            visit(name)
        return tuple(names)

    def freeze(self, request: ReplaceRequest) -> FrozenReplaceSource:
        context_catalog = tuple(self._store.list_context_names())
        names = self._scope_names(request)
        frames: list[_StoreReplaceFrame] = []
        frozen: list[FrozenReplaceContext] = []
        for name in names:
            context = self._store.load_for_update(name)
            digest = context._store_digest or context_record_digest(context)
            memories = tuple(
                ReplaceSourceMemory(uid=item.uid, content=item.content)
                for item in context.iter_items()
                if isinstance(item, Memory)
            )
            frames.append(_StoreReplaceFrame(context, digest))
            frozen.append(
                FrozenReplaceContext(
                    name=context.name,
                    uid=context.uid,
                    digest=digest,
                    memories=memories,
                )
            )
        return FrozenReplaceSource(
            contexts=tuple(frozen),
            token=_StoreReplaceToken(
                owner=self._owner,
                operation_uid=str(uuid.uuid4()),
                frames=tuple(frames),
                context_catalog=context_catalog,
            ),
        )

    def _token(self, plan: FrozenReplacePlan) -> _StoreReplaceToken:
        token = plan.token
        if not isinstance(token, _StoreReplaceToken) or token.owner is not self._owner:
            raise ReplaceError("Replace plan belongs to a different runtime.")
        expected = tuple(
            (frame.context.name, frame.context.uid, frame.expected_digest)
            for frame in token.frames
        )
        actual = tuple(
            (context.context_name, context.context_uid, context.context_digest)
            for context in plan.contexts
        )
        if actual != expected:
            raise ReplaceError("Replace plan no longer matches its opaque source.")
        return token

    def _revalidate_without_write(self, token: _StoreReplaceToken) -> None:
        if tuple(self._store.list_context_names()) != token.context_catalog:
            raise ReplaceStalePlanError(
                "The local Context namespace changed during Replace execution."
            )
        for frame in token.frames:
            try:
                current = self._store.load_direct(frame.context.name)
            except FileNotFoundError as error:
                raise ReplaceStalePlanError(
                    f"Replace Context '{frame.context.name}' no longer exists."
                ) from error
            if (
                current.uid != frame.context.uid
                or context_record_digest(current) != frame.expected_digest
            ):
                raise ReplaceStalePlanError(
                    f"Replace Context '{frame.context.name}' changed during execution."
                )

    def apply(self, plan: FrozenReplacePlan) -> ReplaceApplyResult:
        token = self._token(plan)
        changed_contexts = tuple(
            context for context in plan.contexts if context.changed_matches
        )
        if not changed_contexts:
            self._revalidate_without_write(token)
            return _result(plan, checkpoints=())

        frames = {frame.context.name: frame for frame in token.frames}
        changed_identities = tuple(
            {
                "uid": context.context_uid,
                "name": context.context_name,
            }
            for context in changed_contexts
        )
        description = (
            f"Replaced {plan.occurrence_count} occurrence(s) in "
            f"{plan.changed_memory_count} Memory/ies across "
            f"{len(changed_contexts)} Context(s)."
        )
        entries: list[tuple[Context, AutoCheckpoint, str]] = []
        for context_plan in changed_contexts:
            frame = frames[context_plan.context_name]
            for change in context_plan.changed_matches:
                current = frame.context.memories.get(change.memory_uid)
                if (
                    not isinstance(current, Memory)
                    or current.content != change.before_content
                ):
                    raise ReplaceError(
                        "Replace opaque source changed during execution."
                    )
                frame.context.replace(
                    Memory(uid=change.memory_uid, content=change.after_content)
                )
            entries.append(
                (
                    frame.context,
                    AutoCheckpoint(
                        command="replace",
                        args={
                            "replace": {
                                "version": 1,
                                "operation_uid": token.operation_uid,
                                "plan_digest": plan.plan_digest,
                                # Checkpoint snapshots already retain before/after
                                # content. Avoid duplicating redacted literals in
                                # searchable command metadata.
                                "pattern_digest": hashlib.sha256(
                                    plan.request.pattern.encode("utf-8")
                                ).hexdigest(),
                                "replacement_digest": hashlib.sha256(
                                    plan.request.replacement.encode("utf-8")
                                ).hexdigest(),
                                "mode": plan.request.mode,
                                "ignore_case": plan.request.ignore_case,
                                "occurrence_count": plan.occurrence_count,
                                "changed_memory_count": plan.changed_memory_count,
                            },
                            "command_contexts": list(changed_identities),
                        },
                        description=description,
                    ),
                    frame.expected_digest,
                )
            )
        source_bindings = tuple(
            (frame.context.name, frame.context.uid, frame.expected_digest)
            for frame in token.frames
        )
        try:
            checkpoints = self._store.save_context_command_batch(
                entries,
                source_bindings=source_bindings,
                expected_context_catalog=token.context_catalog,
            )
        except ConcurrentContextUpdateError as error:
            message = str(error).replace(
                "after the command was reviewed",
                "during Replace execution",
            )
            raise ReplaceStalePlanError(message) from error
        receipts = tuple(
            ReplaceCheckpoint(
                context_name=context.context_name,
                context_uid=context.context_uid,
                checkpoint_uid=checkpoint.uid,
            )
            for context, checkpoint in zip(changed_contexts, checkpoints, strict=True)
        )
        return _result(plan, checkpoints=receipts)


def _result(
    plan: FrozenReplacePlan,
    *,
    checkpoints: tuple[ReplaceCheckpoint, ...],
) -> ReplaceApplyResult:
    return ReplaceApplyResult(
        plan_digest=plan.plan_digest,
        applied=bool(checkpoints),
        scanned_context_count=plan.scanned_context_count,
        scanned_memory_count=plan.scanned_memory_count,
        matched_memory_count=plan.matched_memory_count,
        changed_memory_count=plan.changed_memory_count,
        occurrence_count=plan.occurrence_count,
        checkpoints=checkpoints,
    )


def plan_replace_with_store(
    request: ReplaceRequest,
    *,
    store: MemoryStore,
) -> tuple[FrozenReplacePlan, MemoryStoreReplacePort]:
    port = MemoryStoreReplacePort(store)
    return plan_replace(request, port=port), port


def execute_replace_plan(
    plan: FrozenReplacePlan,
    *,
    port: MemoryStoreReplacePort,
) -> ReplaceApplyResult:
    return apply_replace(plan, port=port)


def execute_replace_with_store(
    request: ReplaceRequest,
    *,
    store: MemoryStore,
) -> ReplaceApplyResult:
    """Freeze and atomically apply one deterministic request in one turn.

    The frozen plan remains an internal concurrency boundary. Human command
    adapters do not need to expose a second approval step for an exact,
    provider-free operation whose complete effect is immediately Undoable.
    """

    plan, port = plan_replace_with_store(request, store=store)
    return execute_replace_plan(plan, port=port)


__all__ = [
    "MemoryStoreReplacePort",
    "execute_replace_plan",
    "execute_replace_with_store",
    "plan_replace_with_store",
]
