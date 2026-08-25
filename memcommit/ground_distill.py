"""Ground adapter over the operation-independent Distill use case."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
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
from memcommit.ground_workspace_runtime import (
    ground_workspace_exists,
    load_ground_workspace,
)
from memcommit.ground_workspace_projection import (
    GroundWorkspaceProjectionError,
    project_ordinary_memories,
)
from memcommit.store import MemoryStore, ground_session_record_digest
from memcommit.summarize import SummaryFrame, collect_summary_scope
from memcommit.operations.summarize.application import (
    FrozenSummarySource,
    SummarizeRequest,
)


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
class FrozenGroundWorkspaceDistill:
    """Exact consumed Goal, Example, and Context Memories from one workspace."""

    ground_name: str
    ground_uid: str
    ground_revision: int
    ground_digest: str
    candidate_frame: SummaryFrame
    request: DistillRequest
    source_kind: Literal["GROUND_WORKSPACE_INPUTS"] = "GROUND_WORKSPACE_INPUTS"
    example_frame: SummaryFrame | None = None


@dataclass(frozen=True)
class GroundDistillResult:
    frozen: FrozenGroundDistill | FrozenGroundWorkspaceDistill
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
) -> FrozenGroundDistill | FrozenGroundWorkspaceDistill:
    """Freeze Ground identity and its exact candidate Context before inference."""

    if ground_workspace_exists(store, ground_name):
        return _freeze_ground_workspace_distill(store, ground_name)

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


def _freeze_ground_workspace_distill(
    store: MemoryStore,
    ground_name: str,
) -> FrozenGroundWorkspaceDistill:
    workspace = load_ground_workspace(store, ground_name)
    try:
        goals = project_ordinary_memories(
            workspace.goals,
            operation="Ground workspace Distill",
        )
        examples = project_ordinary_memories(
            workspace.examples,
            operation="Ground workspace Distill",
        )
    except GroundWorkspaceProjectionError as error:
        raise DistillError(str(error)) from error
    if len(goals) > 1:
        raise DistillError(
            "Ground workspace Distill requires zero or one Goal Memory."
        )
    contexts_prefix = workspace.contexts.name + "/"
    context_frame = (
        workspace.contexts,
        *(
            store.load_direct(name)
            for name in store.list_context_names()
            if name.startswith(contexts_prefix)
        ),
    )
    try:
        for context in context_frame:
            project_ordinary_memories(
                context,
                operation="Ground workspace Distill",
            )
    except GroundWorkspaceProjectionError as error:
        raise DistillError(str(error)) from error
    # Use the checked ordinary-Memory projection for Examples rather than
    # relying on Summary's permissive typed-item filtering.
    checked_examples = Context(
        uid=workspace.examples.uid,
        name=workspace.examples.name,
    )
    for memory in examples:
        checked_examples.add(memory)
    frame = collect_summary_scope(
        (checked_examples, *context_frame),
        root_context_uid=workspace.examples.uid,
        root_context_name=workspace.examples.name,
        include_descendants=False,
        follow_embeds=False,
    )
    if not frame.sources:
        raise DistillError(
            "Ground workspace Distill requires an ordinary Memory in "
            "/examples or /contexts."
        )
    digest = hashlib.sha256(
        json.dumps(
            {
                "workspace_uid": workspace.uid,
                "goal": (
                    None
                    if not goals
                    else {"uid": goals[0].uid, "content": goals[0].content}
                ),
                "sources": [
                    {
                        "context_uid": source.context_uid,
                        "memory_uid": source.memory_uid,
                        "content": source.content,
                    }
                    for source in frame.sources
                ],
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return FrozenGroundWorkspaceDistill(
        ground_name=workspace.name,
        ground_uid=workspace.uid,
        ground_revision=workspace.manifest.revision,
        ground_digest=digest,
        candidate_frame=frame,
        request=DistillRequest(
            context_locator=workspace.examples.name,
            goal=goals[0].content if goals else None,
        ),
        example_frame=frame,
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


def _revalidate_ground_workspace(
    frozen: FrozenGroundWorkspaceDistill,
    store: MemoryStore,
) -> None:
    current = _freeze_ground_workspace_distill(store, frozen.ground_name)
    if (
        current.ground_uid != frozen.ground_uid
        or current.ground_digest != frozen.ground_digest
        or current.request != frozen.request
        or current.candidate_frame != frozen.candidate_frame
    ):
        raise DistillError(
            "The consumed Ground workspace Memories changed while Distill was running."
        )


def execute_ground_distill(
    frozen: FrozenGroundDistill | FrozenGroundWorkspaceDistill,
    *,
    store: MemoryStore,
    provider_factory: GroundDistillProviderFactory,
) -> GroundDistillResult:
    """Run the shared application without mutating Ground or bound Contexts."""

    if not isinstance(frozen, (FrozenGroundDistill, FrozenGroundWorkspaceDistill)):
        raise TypeError("Ground Distill requires a frozen request.")
    if isinstance(frozen, FrozenGroundWorkspaceDistill):
        _revalidate_ground_workspace(frozen, store)

        class _GroundWorkspaceSourcePort:
            def freeze(self, request: SummarizeRequest) -> FrozenSummarySource:
                if (
                    request.context_locator != frozen.request.context_locator
                    or request.include_descendants
                    or request.follow_embeds
                ):
                    raise DistillError(
                        "Ground workspace Distill changed its frozen inputs."
                    )
                _revalidate_ground_workspace(frozen, store)
                return FrozenSummarySource(
                    frame=frozen.candidate_frame,
                    token=frozen.ground_digest,
                )

            def revalidate(self, source: FrozenSummarySource) -> SummaryFrame:
                if (
                    source.token != frozen.ground_digest
                    or source.frame != frozen.candidate_frame
                ):
                    raise DistillError(
                        "Ground workspace Distill input binding is invalid."
                    )
                _revalidate_ground_workspace(frozen, store)
                return frozen.candidate_frame

        @contextmanager
        def workspace_provider_session() -> Iterator[DistillProvider]:
            yield provider_factory()

        result = run_distill(
            frozen.request,
            source_port=_GroundWorkspaceSourcePort(),
            provider_session_factory=workspace_provider_session,
        )
        _revalidate_ground_workspace(frozen, store)
        return GroundDistillResult(frozen=frozen, distill=result)
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
    "FrozenGroundWorkspaceDistill",
    "GroundDistillResult",
    "execute_ground_distill",
    "freeze_ground_distill",
]
