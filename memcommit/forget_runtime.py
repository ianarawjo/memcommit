"""Store, authority, provider, and checkpoint adapters for Forget."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from memcommit.authority.access import (
    ContextAccess,
    authorized_context_mutation,
    grant_checkpoint_args,
    resolve_context_access,
)
from memcommit.config import Config
from memcommit.context import AutoCheckpoint, Context
from memcommit.forget_application import (
    ForgetAnalysisRequest,
    ForgetAnalysisResult,
    ForgetApplyReceipt,
    ForgetApplyRequest,
    ForgetApplyResult,
    ForgetProgressObserver,
    ForgetRevisionRequest,
    ForgetSelectionRequest,
    ForgetSessionSnapshot,
    ForgetSourcePort,
    FrozenForgetSource,
    run_forget_analysis,
    run_forget_apply,
    run_forget_revision,
    run_forget_selection,
)
from memcommit.query_provider import CodexChatGPTProvider
from memcommit.semantic.changes import (
    EditChange,
    ProposedChange,
    RemoveChange,
    apply_changes,
)
from memcommit.store import MemoryStore
from memcommit.infrastructure.providers.policy import (
    FORGET_PROVIDER_POLICY,
    resolve_operation_provider_policy,
)
from memcommit.study_action_log import (
    record_provider_connection_finished,
    record_provider_connection_started,
)


FORGET_PROVIDER_MODEL = FORGET_PROVIDER_POLICY.model
FORGET_PROVIDER_REASONING_EFFORT = FORGET_PROVIDER_POLICY.reasoning_effort


def connect_forget_provider() -> CodexChatGPTProvider:
    """Connect Forget's benchmark-selected provisional provider policy."""

    resolved = resolve_operation_provider_policy(
        "forget",
        config=Config(),
    )
    started_at = record_provider_connection_started("forget")
    try:
        provider = CodexChatGPTProvider.connect(
            timeout=resolved.timeout_seconds,
            model=resolved.model,
            reasoning_effort=resolved.reasoning_effort,
        )
    except BaseException as error:
        record_provider_connection_finished(
            "forget",
            started_at,
            failure=error,
        )
        raise
    record_provider_connection_finished(
        "forget",
        started_at,
        provider=provider.identity.provider,
    )
    return provider


@dataclass(frozen=True)
class _ForgetRuntimeToken:
    access: ContextAccess
    context: Context


def _required_permissions(
    changes: Sequence[ProposedChange],
) -> tuple[str, ...]:
    permissions = {
        "DELETE" if isinstance(change, RemoveChange) else "UPDATE"
        for change in changes
    }
    return tuple(sorted(permissions))


def _checkpoint_description(
    instruction: str,
    changes: Sequence[ProposedChange],
) -> str:
    removes = [change for change in changes if isinstance(change, RemoveChange)]
    edits = [change for change in changes if isinstance(change, EditChange)]
    parts: list[str] = []
    if removes:
        parts.append(
            f'removed "{removes[0].content[:40]}"'
            if len(removes) == 1
            else f"removed {len(removes)}"
        )
    if edits:
        parts.append(
            f'edited "{edits[0].old_content[:40]}"'
            if len(edits) == 1
            else f"edited {len(edits)}"
        )
    return f'Forgot ({instruction[:40]}): {", ".join(parts)}'


def _checkpoint_effects(
    changes: Sequence[ProposedChange],
) -> list[dict[str, object]]:
    """Persist the exact applied pre/post image for later read-only Review."""

    effects: list[dict[str, object]] = []
    for change in changes:
        if isinstance(change, RemoveChange):
            effects.append(
                {
                    "kind": "REMOVE",
                    "memory_uid": change.uid,
                    "before": change.content,
                    "after": None,
                    "reason": change.reason,
                }
            )
        elif isinstance(change, EditChange):
            effects.append(
                {
                    "kind": "EDIT",
                    "memory_uid": change.uid,
                    "before": change.old_content,
                    "after": change.new_content,
                    "reason": change.reason,
                }
            )
    return effects


@dataclass
class MemoryStoreForgetSourcePort(ForgetSourcePort):
    """Freeze one direct readable Source and later mutate only that binding."""

    store: MemoryStore
    current_name: str | None = None
    _frozen_request: ForgetAnalysisRequest | None = None
    _frozen_source: FrozenForgetSource | None = None

    def __post_init__(self) -> None:
        if self.current_name is None and self.store.state_file.exists():
            self.current_name = self.store.current_context_name()

    def freeze(self, request: ForgetAnalysisRequest) -> FrozenForgetSource:
        if self._frozen_request is not None:
            if request != self._frozen_request or self._frozen_source is None:
                raise ValueError(
                    "One Forget runtime cannot freeze two different Sources."
                )
            return self._frozen_source
        access = resolve_context_access(
            self.store,
            request.source_locator,
            current_name=self.current_name,
            required_permission="READ",
        )
        context = access.store.load_direct(access.context_name)
        source = FrozenForgetSource(
            context=context,
            display_name=access.display_name,
            granted=access.is_granted,
            _runtime_token=_ForgetRuntimeToken(access=access, context=context),
        )
        self._frozen_request = request
        self._frozen_source = source
        return source

    def apply(
        self,
        source: FrozenForgetSource,
        instruction: str,
        changes: Sequence[ProposedChange],
    ) -> ForgetApplyReceipt:
        token = source._runtime_token
        if (
            not isinstance(token, _ForgetRuntimeToken)
            or token.context is not source.context
            or token.context.uid != source.context.uid
            or token.access.display_name != source.display_name
            or token.access.is_granted != source.granted
        ):
            raise ValueError("Forget Source does not belong to this runtime binding.")
        removed = sum(isinstance(change, RemoveChange) for change in changes)
        edited = sum(isinstance(change, EditChange) for change in changes)
        if removed + edited != len(changes) or not changes:
            raise ValueError("Forget Apply requires supported reviewed changes.")
        with authorized_context_mutation(
            token.access,
            required_permissions=_required_permissions(changes),
        ):
            apply_changes(token.context, list(changes))
            checkpoint = token.access.store.save(
                token.context,
                AutoCheckpoint(
                    command="forget",
                    args={
                        "query": instruction,
                        "effects": _checkpoint_effects(changes),
                        **grant_checkpoint_args(token.access),
                    },
                    description=_checkpoint_description(instruction, changes),
                ),
            )
        if checkpoint is None:
            raise RuntimeError("Forget Apply did not create its checkpoint.")
        return ForgetApplyReceipt(
            source_name=source.display_name,
            source_context_uid=source.context.uid,
            removed_count=removed,
            edited_count=edited,
            checkpoint_uid=checkpoint.uid,
            undo_available=not source.granted,
            granted=source.granted,
        )


def execute_forget_analysis(
    request: ForgetAnalysisRequest,
    *,
    store: MemoryStore,
    provider_factory=connect_forget_provider,
    progress_observer: ForgetProgressObserver | None = None,
) -> ForgetAnalysisResult:
    """Run one authority-first analysis through production adapters."""

    source_port = MemoryStoreForgetSourcePort(store)
    return run_forget_analysis(
        request,
        source_port=source_port,
        provider_factory=provider_factory,
        progress_observer=progress_observer,
    )


def execute_forget_selection(
    request: ForgetSelectionRequest,
) -> ForgetSessionSnapshot:
    return run_forget_selection(request)


def execute_forget_revision(
    request: ForgetRevisionRequest,
    *,
    provider_factory=connect_forget_provider,
) -> ForgetSessionSnapshot:
    return run_forget_revision(request, provider_factory=provider_factory)


def execute_forget_apply(
    request: ForgetApplyRequest,
    *,
    source_port: ForgetSourcePort,
) -> ForgetApplyResult:
    return run_forget_apply(request, source_port=source_port)


__all__ = [
    "FORGET_PROVIDER_MODEL",
    "FORGET_PROVIDER_REASONING_EFFORT",
    "MemoryStoreForgetSourcePort",
    "connect_forget_provider",
    "execute_forget_analysis",
    "execute_forget_apply",
    "execute_forget_revision",
    "execute_forget_selection",
]
