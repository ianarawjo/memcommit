"""Ground adapter over the operation-independent Distill use case."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Literal, Protocol

from memcommit.context import Context, Memory
from memcommit.distill import DistillError, DistillProvider
from memcommit.distill_application import (
    DistillRequest,
    DistillResult,
    run_distill,
)
from memcommit.distill_runtime import execute_distill
from memcommit.ground import (
    GROUND_PROPOSITION_SCHEMA_VERSION,
    GroundFrame,
    GroundSession,
    context_frame_digest,
    is_bound_ground_schema,
)
from memcommit.store import MemoryStore, ground_session_record_digest
from memcommit.summarize import SummaryFrame, collect_summary_scope
from memcommit.summarize_application import FrozenSummarySource, SummarizeRequest


class GroundDistillProviderFactory(Protocol):
    def __call__(self) -> DistillProvider:
        """Construct the same provider used by standalone Distill."""


@dataclass(frozen=True)
class FrozenGroundDistill:
    """One exact Ground and candidate frame projected into Distill."""

    ground_name: str
    ground_uid: str
    ground_revision: int
    ground_digest: str
    candidate_frame: GroundFrame
    request: DistillRequest
    source_kind: Literal["GROUND_EXAMPLES", "LEGACY_CANDIDATE_CONTEXT"]
    example_frame: SummaryFrame | None = None


@dataclass(frozen=True)
class GroundDistillResult:
    frozen: FrozenGroundDistill
    distill: DistillResult


def _working_frame(session) -> GroundFrame:
    if not is_bound_ground_schema(session.schema_version):
        raise DistillError("Ground Distill requires a bound Ground.")
    if session.status != "OPEN":
        raise DistillError("Ground Distill requires an open Ground.")
    frames = tuple(
        frame for frame in session.frames if frame.role == "WORKING_CANDIDATES"
    )
    if len(frames) != 1:
        raise DistillError("Ground Distill requires one working-candidate frame.")
    return frames[0]


def _validate_candidate_frame(store: MemoryStore, frame: GroundFrame) -> None:
    try:
        context = store.load_direct(frame.context_name)
    except FileNotFoundError as error:
        raise DistillError(
            f"Bound Context '{frame.context_name}' no longer exists."
        ) from error
    direct_items = tuple(context.iter_items())
    if (
        context.uid != frame.context_uid
        or context_frame_digest(context) != frame.context_digest
        or sum(isinstance(item, Memory) for item in direct_items)
        != frame.direct_memory_count
        or len(direct_items) != frame.direct_item_count
    ):
        raise DistillError(
            f"Bound Context '{frame.context_name}' changed after Ground binding."
        )


def _included_example_frame(
    session: GroundSession,
    candidate_frame: GroundFrame,
) -> SummaryFrame | None:
    """Project active INCLUDE Examples, preserving no-Example compatibility.

    A historical bound Ground may have no Ground Memory records yet; that
    legacy shape keeps the former candidate-Context Distill path. Once any
    Example exists, its durable USE value becomes authoritative and an empty
    INCLUDE set must fail rather than silently falling back to the Context.
    """

    examples = tuple(item for item in session.items if item.kind == "CASE")
    if not examples:
        return None
    included = tuple(
        item
        for item in examples
        if item.status in {"PROPOSED", "ACCEPTED"}
        and item.disposition == "INCLUDE"
    )
    if not included:
        raise DistillError(
            "Ground Distill has no active INCLUDE Examples. Toggle USE on at "
            "least one Example before provider connection."
        )
    context = Context(
        uid=candidate_frame.context_uid,
        name=candidate_frame.context_name,
    )
    for item in included:
        proposition = (
            item.proposition
            if session.schema_version == GROUND_PROPOSITION_SCHEMA_VERSION
            else f"{item.content} -> {item.expected}"
        )
        if not proposition.strip():
            raise DistillError(
                "An active INCLUDE Example has no proposition to Distill."
            )
        # The Ground item UID, rather than its source Context Memory UID,
        # makes citations resolve to the exact reviewed Example and USE state.
        context.add(Memory(uid=item.uid, content=proposition))
    return collect_summary_scope(
        (context,),
        root_context_uid=context.uid,
        root_context_name=context.name,
        include_descendants=False,
        follow_embeds=False,
    )


def freeze_ground_distill(
    store: MemoryStore,
    *,
    ground_name: str,
) -> FrozenGroundDistill:
    """Freeze Ground identity and its exact candidate Context before inference."""

    session = store.load_ground_session(ground_name)
    if session is None:
        raise DistillError(f"Ground '{ground_name}' was not found.")
    frame = _working_frame(session)
    _validate_candidate_frame(store, frame)
    example_frame = _included_example_frame(session, frame)
    return FrozenGroundDistill(
        ground_name=session.contract_name,
        ground_uid=session.uid,
        ground_revision=session.revision,
        ground_digest=ground_session_record_digest(session),
        candidate_frame=frame,
        request=DistillRequest(
            context_locator=frame.context_name,
            goal=session.goal or None,
        ),
        source_kind=(
            "GROUND_EXAMPLES"
            if example_frame is not None
            else "LEGACY_CANDIDATE_CONTEXT"
        ),
        example_frame=example_frame,
    )


def _revalidate_ground(frozen: FrozenGroundDistill, store: MemoryStore) -> None:
    session = store.load_ground_session(frozen.ground_name)
    if (
        session is None
        or session.uid != frozen.ground_uid
        or session.revision != frozen.ground_revision
        or ground_session_record_digest(session) != frozen.ground_digest
        or _working_frame(session) != frozen.candidate_frame
    ):
        raise DistillError("The Ground changed while Distill was running.")
    _validate_candidate_frame(store, frozen.candidate_frame)


def execute_ground_distill(
    frozen: FrozenGroundDistill,
    *,
    store: MemoryStore,
    provider_factory: GroundDistillProviderFactory,
) -> GroundDistillResult:
    """Run the shared application without mutating Ground or bound Contexts."""

    if not isinstance(frozen, FrozenGroundDistill):
        raise TypeError("Ground Distill requires a frozen request.")
    _revalidate_ground(frozen, store)
    if frozen.source_kind == "LEGACY_CANDIDATE_CONTEXT":
        result = execute_distill(
            frozen.request,
            store=store,
            provider_factory=provider_factory,
        )
    else:
        if frozen.example_frame is None:  # pragma: no cover - typed invariant
            raise DistillError("Ground Distill lost its frozen Example frame.")

        class _GroundExampleSourcePort:
            def freeze(self, request: SummarizeRequest) -> FrozenSummarySource:
                if (
                    request.context_locator != frozen.request.context_locator
                    or request.include_descendants
                    or request.follow_embeds
                ):
                    raise DistillError(
                        "Ground Distill Example scope does not match its "
                        "frozen request."
                    )
                _revalidate_ground(frozen, store)
                return FrozenSummarySource(
                    frame=frozen.example_frame,
                    token=frozen.ground_digest,
                )

            def revalidate(self, source: FrozenSummarySource) -> SummaryFrame:
                if (
                    source.token != frozen.ground_digest
                    or source.frame != frozen.example_frame
                ):
                    raise DistillError(
                        "Ground Distill Example binding is invalid."
                    )
                _revalidate_ground(frozen, store)
                return frozen.example_frame

        @contextmanager
        def provider_session() -> Iterator[DistillProvider]:
            yield provider_factory()

        result = run_distill(
            frozen.request,
            source_port=_GroundExampleSourcePort(),
            provider_session_factory=provider_session,
        )
    _revalidate_ground(frozen, store)
    return GroundDistillResult(frozen=frozen, distill=result)


__all__ = [
    "FrozenGroundDistill",
    "GroundDistillResult",
    "execute_ground_distill",
    "freeze_ground_distill",
]
