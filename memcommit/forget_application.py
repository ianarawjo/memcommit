"""Terminal-independent application lifecycle for selective Forget."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
import hashlib
import json
from typing import Literal, Protocol

from memcommit.context import Context, Memory
from memcommit.forget_provider import analyze_forget, revise_forget_analysis
from memcommit.forget_review import ForgetReview, ForgetSelection
from memcommit.semantic.changes import EditChange, ProposedChange, RemoveChange
from memcommit.selective_curation import CurationAnalysis, CurationDecision


class ForgetApplicationError(RuntimeError):
    """A Forget use case could not safely reach its requested outcome."""


@dataclass(frozen=True)
class ForgetAnalysisRequest:
    """One exact direct Source and instruction, independent of CLI/TUI state."""

    source_locator: str | None
    instruction: str

    def __post_init__(self) -> None:
        if self.source_locator is not None and (
            not isinstance(self.source_locator, str)
            or not self.source_locator.strip()
        ):
            raise ForgetApplicationError(
                "Forget Source must be nonblank text when supplied."
            )
        if not isinstance(self.instruction, str) or not self.instruction.strip():
            raise ForgetApplicationError("Forget instruction must be nonblank text.")


@dataclass(frozen=True)
class FrozenForgetSource:
    """Authorized direct Source plus an opaque adapter-owned Apply binding."""

    context: Context
    display_name: str
    granted: bool
    _runtime_token: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.context, Context):
            raise ForgetApplicationError("Forget Source must be a Context.")
        if not isinstance(self.display_name, str) or not self.display_name.strip():
            raise ForgetApplicationError("Forget Source requires a display name.")
        if not isinstance(self.granted, bool):
            raise ForgetApplicationError("Forget granted state must be a boolean.")

    @property
    def memory_count(self) -> int:
        return sum(isinstance(item, Memory) for item in self.context.iter_items())


@dataclass(frozen=True)
class ForgetProviderMessage:
    """One role-ordered provider dialogue entry retained only in this process."""

    role: str
    content: str

    def __post_init__(self) -> None:
        if self.role not in {"system", "user", "assistant"}:
            raise ForgetApplicationError("Invalid Forget provider dialogue role.")
        if not isinstance(self.content, str):
            raise ForgetApplicationError("Invalid Forget provider dialogue content.")

    def to_dict(self) -> dict[str, object]:
        return {"role": self.role, "content": self.content}


def _freeze_history(
    history: Sequence[dict[str, object]],
) -> tuple[ForgetProviderMessage, ...]:
    messages: list[ForgetProviderMessage] = []
    for entry in history:
        role = entry.get("role")
        content = entry.get("content")
        if not isinstance(role, str) or not isinstance(content, str):
            raise ForgetApplicationError(
                "Forget provider dialogue contains an invalid message."
            )
        messages.append(ForgetProviderMessage(role, content))
    return tuple(messages)


def _thaw_history(
    history: Sequence[ForgetProviderMessage],
) -> list[dict[str, object]]:
    return [message.to_dict() for message in history]


def _snapshot_payload(
    source: FrozenForgetSource,
    review: ForgetReview,
    history: Sequence[ForgetProviderMessage],
) -> dict[str, object]:
    return {
        "source": {
            "name": source.display_name,
            "context_name": source.context.name,
            "context_uid": source.context.uid,
            "granted": source.granted,
        },
        "review": {
            "uid": review.uid,
            "revision": review.revision,
            "instruction": review.instruction,
            "overview": review.overview,
            "candidates": [
                {
                    "uid": candidate.uid,
                    "source_uid": candidate.source.uid,
                    "source_content": candidate.source.content,
                    "decision": {
                        "action": candidate.decision.action,
                        "variant": candidate.decision.variant,
                        "proposed_content": candidate.decision.proposed_content,
                        "rationale": candidate.decision.rationale,
                        "criterion_uids": candidate.decision.criterion_uids,
                    },
                    "selection": candidate.selection,
                    "custom_content": candidate.custom_content,
                }
                for candidate in review.candidates
            ],
        },
        "history": [
            {"role": message.role, "content": message.content}
            for message in history
        ],
    }


def forget_snapshot_version(
    source: FrozenForgetSource,
    review: ForgetReview,
    history: Sequence[ForgetProviderMessage],
) -> str:
    payload = json.dumps(
        _snapshot_payload(source, review, history),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class ForgetSessionSnapshot:
    """One process-local reviewed state with an opaque optimistic token."""

    source: FrozenForgetSource
    review: ForgetReview
    history: tuple[ForgetProviderMessage, ...]
    version_token: str

    def __post_init__(self) -> None:
        if (
            self.review.context_name != self.source.context.name
            or self.review.context_uid != self.source.context.uid
        ):
            raise ForgetApplicationError(
                "Forget review does not match its frozen Source."
            )
        expected = forget_snapshot_version(self.source, self.review, self.history)
        if self.version_token != expected:
            raise ForgetApplicationError("Forget snapshot version is invalid.")


def _snapshot(
    source: FrozenForgetSource,
    review: ForgetReview,
    history: tuple[ForgetProviderMessage, ...],
) -> ForgetSessionSnapshot:
    return ForgetSessionSnapshot(
        source=source,
        review=review,
        history=history,
        version_token=forget_snapshot_version(source, review, history),
    )


ForgetAnalysisStage = Literal[
    "SOURCE_FROZEN",
    "CONNECTING_PROVIDER",
    "ANALYZING",
]


@dataclass(frozen=True)
class ForgetAnalysisProgress:
    stage: ForgetAnalysisStage
    source_count: int


ForgetProgressObserver = Callable[[ForgetAnalysisProgress], None]


@dataclass(frozen=True)
class ForgetAnalysisResult:
    snapshot: ForgetSessionSnapshot
    provider_used: bool


@dataclass(frozen=True)
class ForgetSelectionRequest:
    snapshot: ForgetSessionSnapshot
    candidate_uid: str
    selection: ForgetSelection
    custom_content: str = ""


@dataclass(frozen=True)
class ForgetRevisionRequest:
    snapshot: ForgetSessionSnapshot
    feedback: str


@dataclass(frozen=True)
class ForgetApplyRequest:
    snapshot: ForgetSessionSnapshot


@dataclass(frozen=True)
class ForgetApplyReceipt:
    source_name: str
    source_context_uid: str
    removed_count: int
    edited_count: int
    checkpoint_uid: str | None
    undo_available: bool
    granted: bool

    def __post_init__(self) -> None:
        if self.removed_count < 0 or self.edited_count < 0:
            raise ForgetApplicationError("Forget effect counts cannot be negative.")
        if self.granted and self.undo_available:
            raise ForgetApplicationError(
                "Granted Forget receipts cannot advertise local Undo."
            )

    @property
    def changed_count(self) -> int:
        return self.removed_count + self.edited_count


@dataclass(frozen=True)
class ForgetApplyResult:
    snapshot: ForgetSessionSnapshot
    receipt: ForgetApplyReceipt
    applied: bool


class ForgetSourcePort(Protocol):
    """Freeze one readable Source and own its later exact mutation boundary."""

    def freeze(self, request: ForgetAnalysisRequest) -> FrozenForgetSource:
        """Resolve READ authority and return the complete direct Source."""

    def apply(
        self,
        source: FrozenForgetSource,
        instruction: str,
        changes: Sequence[ProposedChange],
    ) -> ForgetApplyReceipt:
        """Revalidate and atomically publish the exact reviewed changes."""


class ForgetProviderFactory(Protocol):
    def __call__(self) -> object:
        """Construct one provider after Source authority has been frozen."""


def _observe(
    observer: ForgetProgressObserver | None,
    stage: ForgetAnalysisStage,
    source: FrozenForgetSource,
) -> None:
    if observer is not None:
        observer(ForgetAnalysisProgress(stage, source.memory_count))


def run_forget_analysis(
    request: ForgetAnalysisRequest,
    *,
    source_port: ForgetSourcePort,
    provider_factory: ForgetProviderFactory,
    progress_observer: ForgetProgressObserver | None = None,
) -> ForgetAnalysisResult:
    """Freeze, analyze, and return one process-local complete review."""

    source = source_port.freeze(request)
    _observe(progress_observer, "SOURCE_FROZEN", source)
    if source.memory_count == 0:
        analysis = CurationAnalysis(
            overview="The Source Context has no direct Memories to review.",
            decisions=(),
        )
        history: list[dict[str, object]] = []
        provider_used = False
    else:
        _observe(progress_observer, "CONNECTING_PROVIDER", source)
        provider = provider_factory()
        _observe(progress_observer, "ANALYZING", source)
        analysis, history = analyze_forget(
            source.context,
            request.instruction,
            provider,
        )
        provider_used = True
    review = ForgetReview.create(source.context, request.instruction, analysis)
    snapshot = _snapshot(source, review, _freeze_history(history))
    return ForgetAnalysisResult(snapshot=snapshot, provider_used=provider_used)


def run_forget_selection(
    request: ForgetSelectionRequest,
) -> ForgetSessionSnapshot:
    """Apply one exact local review decision without provider or Store effects."""

    if not isinstance(request.candidate_uid, str) or not request.candidate_uid:
        raise ForgetApplicationError("Forget candidate UID must be nonblank text.")
    review = request.snapshot.review.select(
        request.candidate_uid,
        request.selection,
        request.custom_content,
    )
    return _snapshot(request.snapshot.source, review, request.snapshot.history)


def prepare_forget_snapshot(
    source: FrozenForgetSource,
    instruction: str,
    changes: Sequence[ProposedChange],
) -> ForgetSessionSnapshot:
    """Validate a legacy sparse proposal and recover a complete review ledger.

    Historical command tests and ``ops.forget`` callers return only changed
    Memories.  The application boundary requires exhaustive disposition, so
    this compatibility path reconstructs explicit KEEP decisions and rejects
    any proposal that does not exactly match the frozen Source.
    """

    by_uid: dict[str, ProposedChange] = {}
    for change in changes:
        if change.uid in by_uid:
            raise ForgetApplicationError("Duplicate prepared Forget change.")
        by_uid[change.uid] = change
    decisions: list[CurationDecision] = []
    source_uids: set[str] = set()
    for item in source.context.iter_items():
        if not isinstance(item, Memory):
            continue
        source_uids.add(item.uid)
        change = by_uid.get(item.uid)
        if change is None:
            decisions.append(
                CurationDecision(
                    source_uid=item.uid,
                    action="KEEP",
                    variant="KEEP",
                    proposed_content=item.content,
                    rationale="The prepared review keeps this Memory unchanged.",
                    criterion_uids=("forget-request",),
                )
            )
        elif isinstance(change, RemoveChange) and change.content == item.content:
            decisions.append(
                CurationDecision(
                    source_uid=item.uid,
                    action="DROP",
                    variant="DELETE",
                    proposed_content="",
                    rationale=change.reason,
                    criterion_uids=("forget-request",),
                )
            )
        elif (
            isinstance(change, EditChange)
            and change.old_content == item.content
            and change.new_content.strip()
        ):
            decisions.append(
                CurationDecision(
                    source_uid=item.uid,
                    action="TRANSFORM",
                    variant="EDIT",
                    proposed_content=change.new_content,
                    rationale=change.reason,
                    criterion_uids=("forget-request",),
                )
            )
        else:
            raise ForgetApplicationError(
                "Prepared Forget changes do not match the frozen Source."
            )
    if set(by_uid) != source_uids & set(by_uid):
        raise ForgetApplicationError(
            "Prepared Forget changes contain an unavailable Source Memory."
        )
    review = ForgetReview.create(
        source.context,
        instruction,
        CurationAnalysis(
            overview="A prepared Forget review covers the complete Source frame.",
            decisions=tuple(decisions),
        ),
    )
    return _snapshot(source, review, ())


def run_forget_revision(
    request: ForgetRevisionRequest,
    *,
    provider_factory: ForgetProviderFactory,
) -> ForgetSessionSnapshot:
    """Run one whole-frame provider revision over the original frozen Source."""

    if not isinstance(request.feedback, str) or not request.feedback.strip():
        raise ForgetApplicationError("Forget revision feedback must be nonblank text.")
    if not request.snapshot.history:
        raise ForgetApplicationError(
            "An empty-Source Forget review has no provider dialogue to revise."
        )
    provider = provider_factory()
    analysis, history = revise_forget_analysis(
        request.feedback,
        provider,
        _thaw_history(request.snapshot.history),
        request.snapshot.source.context,
    )
    review = request.snapshot.review.revise(
        request.snapshot.source.context,
        analysis,
    )
    return _snapshot(
        request.snapshot.source,
        review,
        _freeze_history(history),
    )


def _effect_counts(
    changes: Sequence[ProposedChange],
) -> tuple[int, int]:
    removed = sum(isinstance(change, RemoveChange) for change in changes)
    edited = sum(isinstance(change, EditChange) for change in changes)
    if removed + edited != len(changes):
        raise ForgetApplicationError("Forget review produced an unsupported change.")
    return removed, edited


def run_forget_apply(
    request: ForgetApplyRequest,
    *,
    source_port: ForgetSourcePort,
) -> ForgetApplyResult:
    """Apply one exact reviewed sparse change set or return an explicit no-op."""

    snapshot = request.snapshot
    changes = tuple(snapshot.review.changes())
    removed, edited = _effect_counts(changes)
    if not changes:
        receipt = ForgetApplyReceipt(
            source_name=snapshot.source.display_name,
            source_context_uid=snapshot.source.context.uid,
            removed_count=0,
            edited_count=0,
            checkpoint_uid=None,
            undo_available=False,
            granted=snapshot.source.granted,
        )
        return ForgetApplyResult(snapshot=snapshot, receipt=receipt, applied=False)

    receipt = source_port.apply(
        snapshot.source,
        snapshot.review.instruction,
        changes,
    )
    if (
        receipt.source_name != snapshot.source.display_name
        or receipt.source_context_uid != snapshot.source.context.uid
        or receipt.removed_count != removed
        or receipt.edited_count != edited
        or receipt.granted != snapshot.source.granted
        or receipt.checkpoint_uid is None
    ):
        raise ForgetApplicationError(
            "Forget Apply returned a receipt outside the reviewed Source and effects."
        )
    return ForgetApplyResult(snapshot=snapshot, receipt=receipt, applied=True)


__all__ = [
    "ForgetAnalysisProgress",
    "ForgetAnalysisRequest",
    "ForgetAnalysisResult",
    "ForgetApplicationError",
    "ForgetApplyReceipt",
    "ForgetApplyRequest",
    "ForgetApplyResult",
    "ForgetProviderMessage",
    "ForgetRevisionRequest",
    "ForgetSelectionRequest",
    "ForgetSessionSnapshot",
    "ForgetSourcePort",
    "FrozenForgetSource",
    "forget_snapshot_version",
    "prepare_forget_snapshot",
    "run_forget_analysis",
    "run_forget_apply",
    "run_forget_revision",
    "run_forget_selection",
]
