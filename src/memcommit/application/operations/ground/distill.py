"""Ground adapter over the operation-independent Distill use case."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
from typing import Iterator, Literal, Protocol

from memcommit.core.context import Context
from memcommit.application.operations.semantic_updates.derive.distill.model import DistillError, DistillProvider
from memcommit.application.operations.semantic_updates.derive.distill.model import (
    ensure_distill_goal_fit_allows_add,
)
from memcommit.application.operations.semantic_updates.derive.distill.application import (
    DistillRequest,
    DistillResult,
    run_distill,
)
from memcommit.application.operations.ground.workspace_runtime import (
    execute_ground_workspace_memories_adoption,
    load_ground_workspace,
)
from memcommit.application.operations.ground.workspace_application import (
    AdoptGroundWorkspaceMemoriesRequest,
    AdoptGroundWorkspaceMemoriesResult,
)
from memcommit.application.operations.ground.workspace_projection import (
    GroundWorkspaceProjectionError,
    project_ordinary_memories,
)
from memcommit.application.capabilities.semantic.goal_focus_runtime import (
    freeze_goal_focus_context,
)
from memcommit.application.capabilities.semantic_result_memorization import (
    FrozenMemorizationTarget,
    freeze_memorization_target,
)
from memcommit.persistence.store import (
    MemoryStore,
    context_record_digest,
)
from memcommit.application.operations.search_explain.synthesize.summarize.model import (
    SummaryFrame,
    collect_summary_scope,
)
from memcommit.application.operations.search_explain.synthesize.summarize.application import (
    FrozenSummarySource,
    SummarizeRequest,
)


class GroundDistillProviderFactory(Protocol):
    def __call__(self) -> DistillProvider:
        """Construct the same provider used by standalone Distill."""


@dataclass(frozen=True)
class FrozenGroundDistill:
    """Exact consumed Goal, Example, and Context Memories from one workspace."""

    ground_name: str
    ground_uid: str
    ground_revision: int
    ground_digest: str
    candidate_frame: SummaryFrame
    request: DistillRequest
    root_digest: str
    target: FrozenMemorizationTarget
    source_bindings: tuple[tuple[str, str, str], ...]
    source_kind: Literal["GROUND_WORKSPACE_INPUTS"] = "GROUND_WORKSPACE_INPUTS"
    example_frame: SummaryFrame | None = None


@dataclass(frozen=True)
class GroundDistillResult:
    frozen: FrozenGroundDistill
    distill: DistillResult


def freeze_ground_distill(
    store: MemoryStore,
    *,
    ground_name: str,
) -> FrozenGroundDistill:
    """Freeze one physical Ground's exact Distill inputs."""

    try:
        workspace = load_ground_workspace(store, ground_name)
    except FileNotFoundError as error:
        raise DistillError(f"Ground {ground_name!r} was not found.") from error
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
        raise DistillError("Ground workspace Distill requires zero or one Goal Memory.")
    goal_focus = (
        freeze_goal_focus_context(
            workspace.goals,
            kind="GROUND",
            require_single=True,
        )
        if goals
        else None
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
    source_contexts = (workspace.examples, *context_frame)
    source_bindings = tuple(
        (context.name, context.uid, context_record_digest(context))
        for context in source_contexts
    )
    if goal_focus is not None:
        assert goal_focus.context_name is not None
        assert goal_focus.context_uid is not None
        assert goal_focus.context_digest is not None
        source_bindings = tuple(
            dict.fromkeys(
                (
                    *source_bindings,
                    (
                        goal_focus.context_name,
                        goal_focus.context_uid,
                        goal_focus.context_digest,
                    ),
                )
            )
        )
    return FrozenGroundDistill(
        ground_name=workspace.name,
        ground_uid=workspace.uid,
        ground_revision=workspace.manifest.revision,
        ground_digest=digest,
        candidate_frame=frame,
        request=DistillRequest(
            context_locator=workspace.examples.name,
            goal_focus=goal_focus,
        ),
        root_digest=context_record_digest(workspace.root),
        target=freeze_memorization_target(store, workspace.rules.name),
        source_bindings=source_bindings,
        example_frame=frame,
    )


def _revalidate_ground(
    frozen: FrozenGroundDistill,
    store: MemoryStore,
    *,
    adoption: bool = False,
) -> None:
    current = freeze_ground_distill(store, ground_name=frozen.ground_name)
    if (
        current.ground_uid != frozen.ground_uid
        or current.ground_digest != frozen.ground_digest
        or current.request != frozen.request
        or current.candidate_frame != frozen.candidate_frame
        or current.source_bindings != frozen.source_bindings
        or (
            adoption
            and (
                current.ground_revision != frozen.ground_revision
                or current.root_digest != frozen.root_digest
                or current.target != frozen.target
            )
        )
    ):
        raise DistillError(
            "The consumed Ground workspace Memories changed while Distill was running."
        )


def execute_ground_distill(
    frozen: FrozenGroundDistill,
    *,
    store: MemoryStore,
    provider_factory: GroundDistillProviderFactory,
) -> GroundDistillResult:
    """Run Distill without mutating the physical Ground workspace."""

    if not isinstance(frozen, FrozenGroundDistill):
        raise TypeError("Ground Distill requires a frozen request.")
    _revalidate_ground(frozen, store)

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
            _revalidate_ground(frozen, store)
            return FrozenSummarySource(
                frame=frozen.candidate_frame,
                token=frozen.ground_digest,
            )

        def revalidate(self, source: FrozenSummarySource) -> SummaryFrame:
            if (
                source.token != frozen.ground_digest
                or source.frame != frozen.candidate_frame
            ):
                raise DistillError("Ground workspace Distill input binding is invalid.")
            _revalidate_ground(frozen, store)
            return frozen.candidate_frame

    @contextmanager
    def workspace_provider_session() -> Iterator[DistillProvider]:
        yield provider_factory()

    result = run_distill(
        frozen.request,
        source_port=_GroundWorkspaceSourcePort(),
        provider_session_factory=workspace_provider_session,
    )
    _revalidate_ground(frozen, store)
    return GroundDistillResult(frozen=frozen, distill=result)


def apply_ground_distill_result(
    result: GroundDistillResult,
    *,
    store: MemoryStore,
) -> AdoptGroundWorkspaceMemoriesResult:
    """Explicitly adopt one unchanged physical-Ground Distill proposal."""

    if not isinstance(result, GroundDistillResult):
        raise DistillError(
            "Distill adoption requires a physical Ground workspace result."
        )
    frozen = result.frozen
    _revalidate_ground(frozen, store, adoption=True)
    ensure_distill_goal_fit_allows_add(result.distill.analysis)
    contents = tuple(rule.content for rule in result.distill.analysis.rules)
    if not contents:
        raise DistillError("Distill produced no Rules to adopt into Ground.")
    return execute_ground_workspace_memories_adoption(
        AdoptGroundWorkspaceMemoriesRequest(
            workspace_name=frozen.ground_name,
            lane="rules",
            contents=contents,
            expected_workspace_uid=frozen.ground_uid,
            expected_revision=frozen.ground_revision,
            expected_root_digest=frozen.root_digest,
            expected_lane_digest=frozen.target.context_digest,
            source_operation="distill",
            analysis_digest=result.distill.analysis.digest,
            source_bindings=frozen.source_bindings,
        ),
        store=store,
    )


__all__ = [
    "FrozenGroundDistill",
    "GroundDistillResult",
    "execute_ground_distill",
    "apply_ground_distill_result",
    "freeze_ground_distill",
]
