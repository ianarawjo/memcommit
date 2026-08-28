"""Context persistence errors and transaction value objects."""

from __future__ import annotations
from dataclasses import dataclass
from memcommit.core.context import Context
from memcommit.application.retained_history.context_lifecycle import (
    ContextLifecycleEvent,
)


class ConcurrentContextUpdateError(RuntimeError):
    """A Context changed after a caller captured its expected record."""


class ContextDeletionCommittedError(RuntimeError):
    """Deletion committed, but one or more post-commit cleanups failed."""

    def __init__(
        self,
        event: ContextLifecycleEvent,
        failures: tuple[tuple[str, Exception], ...],
    ) -> None:
        if not failures:
            raise ValueError("A committed deletion error requires a failure.")
        self.event = event.validated()
        self.failures = failures
        label, failure = failures[0]
        super().__init__(
            "Context deletion committed as lifecycle event "
            f"'{event.event_uid}', but {label} cleanup was incomplete: "
            f"{failure}"
        )


@dataclass(frozen=True)
class ContextBranchMemoryBinding:
    """One exact Source-to-target Memory occurrence created by Branch."""

    source_uid: str
    target_uid: str
    source_content_sha256: str
    target_content_sha256: str


@dataclass(frozen=True)
class ContextBranchBinding:
    """One freshness-bound Source and its newly identified Branch Context."""

    source_name: str
    expected_source_uid: str
    expected_source_digest: str
    expected_history_digest: str
    target: Context
    memories: tuple[ContextBranchMemoryBinding, ...] = ()


@dataclass(frozen=True)
class ContextRenameBinding:
    """One stable ordinary-Context identity in a namespace rename plan."""

    old_name: str
    new_name: str
    context_uid: str


@dataclass(frozen=True)
class ContextRenamePlan:
    """Read-only, freshness-bound preview for one Context namespace rename."""

    old_name: str
    new_name: str
    bindings: tuple[ContextRenameBinding, ...]
    changed_owner_names: tuple[str, ...]
    reference_count: int
    checkpoint_reference_count: int
    ground_frame_count: int
    translation_artifact_count: int
    meld_session_count: int
    current_before: str | None
    current_after: str | None
    graph_digest: str

    @property
    def descendant_count(self) -> int:
        return max(0, len(self.bindings) - 1)


@dataclass(frozen=True)
class ContextRenameResult:
    """Committed counts returned by :meth:`MemoryStore.rename_contexts`."""

    renamed_context_count: int
    changed_owner_count: int
    reference_count: int
    checkpoint_reference_count: int
    ground_frame_count: int
    translation_artifact_count: int
    meld_session_count: int
    current_context: str | None


@dataclass(frozen=True)
class _PreparedContextRename:
    """Validated pre/post images used only inside the store transaction."""

    plan: ContextRenamePlan
    records: dict[str, dict[str, object]]
    post_records: dict[str, dict[str, object]]
    checkpoints: dict[str, dict[str, dict[str, object]]]
    post_checkpoints: dict[str, dict[str, dict[str, object]]]
    state: dict[str, object]
    post_state: dict[str, object]
    ground_records: dict[str, dict[str, object]]
    post_ground_records: dict[str, dict[str, object]]
    translation_records: dict[str, dict[str, object]]
    post_translation_records: dict[str, dict[str, object]]
    meld_records: dict[str, dict[str, object]]
    post_meld_records: dict[str, dict[str, object]]


_NO_CURRENT_CONTEXT_EXPECTATION = object()
