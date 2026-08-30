"""Fit projection and execution for Context-rooted Ground workspaces."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from typing import Callable

from memcommit.core.context import Context
from memcommit.application.operations.fit.ground_report import (
    FitError,
    FitExample,
    FitProvider,
    FitReport,
    FitRule,
    fit_ground_examples,
)
from memcommit.application.operations.fit.coherence import (
    FitCoherenceError,
    FitCoherenceSubject,
    FitContextFrame,
    FitContextMemory,
    FrozenGroundCoherence,
    execute_ground_coherence,
    plan_coherence_checks,
    prepare_ground_coherence,
)
from memcommit.application.operations.ground.contracts import context_frame_digest
from memcommit.application.operations.ground.workspace_model import GroundWorkspace
from memcommit.application.operations.ground.workspace_projection import (
    GroundWorkspaceProjectionError,
    project_ordinary_memories,
)
from memcommit.application.operations.ground.workspace_runtime import (
    load_ground_workspace,
)
from memcommit.application.capabilities.semantic.goal_focus_runtime import (
    freeze_goal_focus_context,
)
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class FrozenGroundWorkspaceFit:
    ground_uid: str
    ground_name: str
    ground_revision: int
    input_digest: str
    rules: tuple[FitRule, ...]
    examples: tuple[FitExample, ...]
    coherence: FrozenGroundCoherence


def freeze_ground_workspace_fit(
    workspace: GroundWorkspace,
    *,
    context_scope: tuple[Context, ...] | None = None,
) -> FrozenGroundWorkspaceFit:
    """Freeze only Goal, Rules, Examples, and explicit Context Memories."""

    try:
        goals = project_ordinary_memories(
            workspace.goals,
            operation="Physical Ground Fit",
        )
        rules = project_ordinary_memories(
            workspace.rules,
            operation="Physical Ground Fit",
        )
        examples = project_ordinary_memories(
            workspace.examples,
            operation="Physical Ground Fit",
        )
    except GroundWorkspaceProjectionError as error:
        raise FitError(str(error)) from error
    context_scope = context_scope or (workspace.contexts,)
    if not context_scope or context_scope[0].uid != workspace.contexts.uid:
        raise FitError("Physical Ground Fit Context scope is invalid.")
    if len(goals) != 1:
        raise FitError("Physical Ground Fit requires exactly one Goal Memory.")
    goal_focus = freeze_goal_focus_context(
        workspace.goals,
        kind="GROUND",
        require_single=True,
    )
    if not rules:
        raise FitError("Physical Ground Fit requires at least one Rule Memory.")
    if not examples:
        raise FitError("Physical Ground Fit requires at least one Example Memory.")
    try:
        context_memories = tuple(
            project_ordinary_memories(
                context,
                operation="Physical Ground Fit",
            )
            for context in context_scope
        )
    except GroundWorkspaceProjectionError as error:
        raise FitError(str(error)) from error

    fit_rules = tuple(
        FitRule(item.uid, f"r{index}", item.content)
        for index, item in enumerate(rules, 1)
    )
    rule_uids = tuple(item.uid for item in fit_rules)
    fit_examples = tuple(
        FitExample(
            uid=item.uid,
            alias=f"e{index}",
            statement=item.content,
            rule_uids=rule_uids,
        )
        for index, item in enumerate(examples, 1)
    )
    context_frames = tuple(
        FitContextFrame(
            uid=context.uid,
            alias=f"k{context_index}",
            name=context.name,
            role="GROUND_CONTEXT",
            digest=context_frame_digest(context),
            memories=tuple(
                FitContextMemory(
                    item.uid,
                    f"k{context_index}m{memory_index}",
                    item.content,
                )
                for memory_index, item in enumerate(memories, 1)
            ),
        )
        for context_index, (context, memories) in enumerate(
            zip(context_scope, context_memories, strict=True),
            1,
        )
    )
    context_aliases = tuple(frame.alias for frame in context_frames)
    subjects = (
        # FitReport v2 identifies the one Goal subject by Ground UID. The
        # exact ordinary Goal Memory UID still participates in input_digest.
        FitCoherenceSubject(
            uid=workspace.uid,
            alias="g1",
            layer="GOAL",
            statement=goal_focus.text,
            context_aliases=context_aliases,
        ),
        *(
            FitCoherenceSubject(
                uid=item.uid,
                alias=f"r{index}",
                layer="RULE",
                statement=item.content,
                context_aliases=context_aliases,
            )
            for index, item in enumerate(rules, 1)
        ),
        *(
            FitCoherenceSubject(
                uid=item.uid,
                alias=f"e{index}",
                layer="EXAMPLE",
                statement=item.content,
                context_aliases=context_aliases,
            )
            for index, item in enumerate(examples, 1)
        ),
    )
    coherence = FrozenGroundCoherence(
        brief=goal_focus.text,
        requirements=(),
        contexts=context_frames,
        subjects=subjects,
        checks=plan_coherence_checks(subjects, context_frames),
    )
    digest_payload = {
        "workspace_uid": workspace.uid,
        "goal": {"uid": goals[0].uid, "content": goals[0].content},
        "rules": [item.to_dict() for item in fit_rules],
        "examples": [item.to_dict() for item in fit_examples],
        "contexts": [context_frame.to_dict() for context_frame in context_frames],
    }
    input_digest = hashlib.sha256(
        json.dumps(
            digest_payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return FrozenGroundWorkspaceFit(
        ground_uid=workspace.uid,
        ground_name=workspace.name,
        ground_revision=workspace.manifest.revision,
        input_digest=input_digest,
        rules=fit_rules,
        examples=fit_examples,
        coherence=coherence,
    )


def workspace_fit_report_is_current(
    store: MemoryStore,
    report: FitReport,
) -> bool:
    """Check one receipt against only the physical Memories it consumed."""

    try:
        workspace = load_ground_workspace(store, report.ground_name)
        frozen = freeze_ground_workspace_fit(
            workspace,
            context_scope=load_ground_workspace_fit_contexts(store, workspace),
        )
    except (FileNotFoundError, FitError, OSError, RuntimeError, ValueError):
        return False
    return (
        frozen.ground_uid == report.ground_uid
        and frozen.input_digest == report.ground_digest
        and frozen.rules == report.rules
        and frozen.examples == report.examples
    )


def execute_ground_workspace_fit(
    *,
    store: MemoryStore,
    ground_name: str,
    provider_factory: Callable[[], FitProvider],
) -> FitReport:
    """Run Example and full graph checks over one exact physical input frame."""

    workspace = load_ground_workspace(store, ground_name)
    frozen = freeze_ground_workspace_fit(
        workspace,
        context_scope=load_ground_workspace_fit_contexts(store, workspace),
    )
    # All local shape, authority-bound projection, and completeness checks run
    # before opening the provider boundary.
    provider = provider_factory()
    report = fit_ground_examples(
        ground_uid=frozen.ground_uid,
        ground_name=frozen.ground_name,
        ground_revision=frozen.ground_revision,
        ground_digest=frozen.input_digest,
        rules=frozen.rules,
        examples=frozen.examples,
        provider=provider,
    )
    try:
        coherence = execute_ground_coherence(
            prepare_ground_coherence(frozen.coherence),
            provider=provider,
        )
    except FitCoherenceError as error:
        raise FitError(str(error)) from error
    if (
        report.provider_identity is not None
        and coherence.provider_identity is not None
        and report.provider_identity != coherence.provider_identity
    ):
        raise FitError("Fit provider identity changed between complete checks.")
    report = replace(
        report,
        coherence=coherence,
        provider_identity=(coherence.provider_identity or report.provider_identity),
    )
    if not workspace_fit_report_is_current(store, report):
        raise FitError(
            "The consumed Ground workspace Memories changed during Fit; "
            "no report was published."
        )
    return report


def load_ground_workspace_fit_contexts(
    store: MemoryStore,
    workspace: GroundWorkspace,
) -> tuple[Context, ...]:
    """Load the explicit `/contexts` lane and its local lexical descendants."""

    prefix = workspace.contexts.name + "/"
    return (
        workspace.contexts,
        *(
            store.load_direct(name)
            for name in store.list_context_names()
            if name.startswith(prefix)
        ),
    )


__all__ = [
    "FrozenGroundWorkspaceFit",
    "execute_ground_workspace_fit",
    "freeze_ground_workspace_fit",
    "load_ground_workspace_fit_contexts",
    "workspace_fit_report_is_current",
]
