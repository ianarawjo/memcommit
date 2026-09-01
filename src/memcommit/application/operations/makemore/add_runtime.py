"""Operation-owned Context preparation and atomic Add for Makemore."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from memcommit.core.context import Memory
from memcommit.application.operations.makemore.model import (
    MakemoreError,
    MakemoreMode,
    MakemoreQualityPolicy,
)
from memcommit.application.operations.makemore.application import (
    MakemoreRequest,
    MakemoreResult,
)
from memcommit.application.capabilities.semantic.goal_focus import FrozenGoalFocus
from memcommit.application.capabilities.semantic.goal_focus_runtime import revalidate_goal_focus
from memcommit.application.operations.makemore.runtime import (
    MakemoreProviderFactory,
    execute_makemore,
)
from memcommit.application.operations.makemore.target_context import (
    FrozenMakemoreTargetContext,
    GRANTED_MAKEMORE_ADD_PERMISSIONS,
    GRANTED_MAKEMORE_AMBIENT_PERMISSIONS,
    authorized_frozen_makemore_target,
    freeze_makemore_target_context,
)
from memcommit.application.capabilities.semantic_result_memorization import (
    FrozenMemorizationTarget,
    SemanticResultMemorizationReceipt,
    freeze_memorization_target,
    memorize_semantic_result,
)
from memcommit.persistence.store import MemoryStore, context_record_digest


MakemoreContextRole = Literal["goal", "rules"]


@dataclass(frozen=True)
class FrozenMakemoreSource:
    """One exact ordinary Context pre-image projected into Makemore."""

    context_name: str
    context_uid: str
    context_digest: str
    role: MakemoreContextRole
    request: MakemoreRequest
    memory_uids: tuple[str, ...]


@dataclass(frozen=True)
class PreparedMakemoreAdd:
    """Exact provider result paired with its already-frozen Add Target."""

    result: MakemoreResult
    target: FrozenMemorizationTarget
    target_context: FrozenMakemoreTargetContext
    source: FrozenMakemoreSource | None = None


def freeze_makemore_context_source(
    store: MemoryStore,
    *,
    context_name: str,
    role: MakemoreContextRole,
    number: int | None = None,
    strict: bool = False,
    goal_focus: FrozenGoalFocus | None = None,
) -> FrozenMakemoreSource:
    """Interpret ordinary direct Memories by invocation role, never by name."""

    if role not in {"goal", "rules"}:
        raise MakemoreError("Makemore --as must be 'goal' or 'rules'.")
    context = store.load_direct(context_name)
    items = tuple(context.iter_items())
    if any(not isinstance(item, Memory) for item in items):
        raise MakemoreError(
            "Context-backed Makemore requires only directly owned ordinary "
            "Memories in its Source."
        )
    memories = tuple(item for item in items if isinstance(item, Memory))
    if role == "goal":
        if len(memories) != 1:
            raise MakemoreError(
                "Makemore --as goal requires exactly one direct Source Memory."
            )
        request = MakemoreRequest(
            goal=memories[0].content,
            goal_focus=goal_focus,
            number=number,
            strict=strict,
        )
    else:
        if not memories:
            raise MakemoreError(
                "Makemore requires at least one direct Source Memory."
            )
        request = MakemoreRequest(
            rules=tuple(item.content for item in memories),
            goal_focus=goal_focus,
            number=number,
            strict=strict,
        )
    return FrozenMakemoreSource(
        context_name=context.name,
        context_uid=context.uid,
        context_digest=context_record_digest(context),
        role=role,
        request=request,
        memory_uids=tuple(item.uid for item in memories),
    )


def _revalidate_source(
    store: MemoryStore,
    source: FrozenMakemoreSource,
) -> None:
    current = store.load_direct(source.context_name)
    if (
        current.uid != source.context_uid
        or context_record_digest(current) != source.context_digest
    ):
        raise MakemoreError(
            f"Source Context '{source.context_name}' changed while Makemore "
            "was running; no generated Memories were added."
        )


def prepare_makemore_add(
    *,
    store: MemoryStore,
    request: MakemoreRequest,
    target_name: str,
    provider_factory: MakemoreProviderFactory,
    source: FrozenMakemoreSource | None = None,
    will_apply: bool = False,
) -> PreparedMakemoreAdd:
    """Freeze Target before inference and return one non-mutating exact plan."""

    target = freeze_memorization_target(store, target_name)
    return prepare_makemore_add_to_frozen_target(
        store=store,
        request=request,
        target=target,
        provider_factory=provider_factory,
        source=source,
        will_apply=will_apply,
    )


def prepare_makemore_add_to_frozen_target(
    *,
    store: MemoryStore,
    request: MakemoreRequest,
    target: FrozenMemorizationTarget,
    provider_factory: MakemoreProviderFactory,
    source: FrozenMakemoreSource | None = None,
    excluded_root_memory_uids: tuple[str, ...] = (),
    will_apply: bool = False,
) -> PreparedMakemoreAdd:
    """Prepare Makemore against a Target frozen before an earlier semantic stage."""

    if source is not None and source.request != request:
        raise MakemoreError("Makemore Source does not match its request.")
    source_exclusions = (
        source.memory_uids
        if source is not None and source.context_uid == target.context_uid
        else ()
    )
    if excluded_root_memory_uids and source is not None:
        raise MakemoreError(
            "Makemore cannot combine direct-Source and derived-Source exclusions."
        )
    exclusions = excluded_root_memory_uids or source_exclusions
    if len(set(exclusions)) != len(exclusions):
        raise MakemoreError("Makemore Source exclusions must be distinct.")
    if request.goal_focus is not None:
        revalidate_goal_focus(store, request.goal_focus)
    target_context = freeze_makemore_target_context(
        store,
        target=target,
        excluded_root_memory_uids=exclusions,
        required_granted_permissions=(
            GRANTED_MAKEMORE_ADD_PERMISSIONS
            if will_apply
            else GRANTED_MAKEMORE_AMBIENT_PERMISSIONS
        ),
    )
    if source is not None:
        _revalidate_source(store, source)
    with authorized_frozen_makemore_target(store, target_context):
        if source is not None:
            _revalidate_source(store, source)
        result = execute_makemore(
            request,
            provider_factory=provider_factory,
            target_context=(
                target_context.semantic if target_context.semantic.items else None
            ),
        )
        if request.goal_focus is not None:
            revalidate_goal_focus(store, request.goal_focus)
        if source is not None:
            _revalidate_source(store, source)
    return PreparedMakemoreAdd(
        result=result,
        target=target,
        target_context=target_context,
        source=source,
    )


def makemore_result_contents(result: MakemoreResult) -> tuple[str, ...]:
    """Return the exact ordered Memory contents represented by one result."""

    analysis = result.analysis
    return (
        tuple(item.content for item in analysis.rules)
        if analysis.mode is MakemoreMode.GOAL_TO_RULES
        else tuple(item.proposition for item in analysis.cases)
    )


def makemore_checkpoint_payload(result: MakemoreResult) -> dict[str, object]:
    """Serialize the stable direct-Makemore portion of an Add receipt."""

    analysis = result.analysis
    proposal_records: list[dict[str, object]] = (
        [
            {
                "proposal_uid": item.uid,
                "content": item.content,
                "rationale": item.rationale,
                "target_context_refs": list(item.target_context_refs),
            }
            for item in analysis.rules
        ]
        if analysis.mode is MakemoreMode.GOAL_TO_RULES
        else [
            {
                "proposal_uid": item.uid,
                "content": item.proposition,
                "expected": item.expected,
                "rationale": item.rationale,
                "case_role": item.case_role,
                "rule_checks": [
                    {
                        "source_rule_index": check.source_rule_index,
                        "evidence": check.evidence,
                    }
                    for check in item.rule_checks
                ],
                "validation": {
                    "source_fit": item.validation.source_fit,
                    "source_fit_reason": item.validation.source_fit_reason,
                    "rule_conformance": item.validation.rule_conformance,
                    "conforming_source_rule_indexes": list(
                        item.validation.conforming_source_rule_indexes
                    ),
                }
                if item.validation is not None
                else None,
                "target_context_refs": list(item.target_context_refs),
            }
            for item in analysis.cases
        ]
    )
    return {
        "analysis_uid": analysis.uid,
        "analysis_digest": analysis.digest,
        "mode": analysis.mode.value,
        "number": analysis.number,
        "verification": "UNVERIFIED",
        "quality_policy": analysis.quality_policy.value,
        "case_validation": (
            (
                "ORDERED_COLLECTION_SOURCE_RULE_CONFORMANCE_AND_SOURCE_FIT"
                if analysis.quality_policy is MakemoreQualityPolicy.STRICT
                else "NOT_RUN"
            )
            if analysis.mode is MakemoreMode.RULES_TO_CASES
            else None
        ),
        "origin": result.origin,
        "overview": analysis.overview,
        "inputs": list(analysis.inputs),
        "goal_focus": (
            None
            if analysis.goal_focus is None
            else analysis.goal_focus.receipt_record()
        ),
        "target_ambient": (
            analysis.target_context.prompt_record()
            if analysis.target_context is not None
            else None
        ),
        "proposals": proposal_records,
    }


def apply_prepared_makemore_add(
    prepared: PreparedMakemoreAdd,
    *,
    store: MemoryStore,
) -> SemanticResultMemorizationReceipt:
    """Append the complete generated proposal set as one Context checkpoint."""

    if not isinstance(prepared, PreparedMakemoreAdd):
        raise TypeError("Makemore Add requires a prepared result.")
    analysis = prepared.result.analysis
    contents = makemore_result_contents(prepared.result)
    source = prepared.source
    source_bindings = (
        ()
        if source is None
        else ((source.context_name, source.context_uid, source.context_digest),)
    )
    goal_focus = analysis.goal_focus
    goal_bindings = (
        ()
        if goal_focus is None or goal_focus.kind == "INLINE"
        else (
            (
                goal_focus.context_name,
                goal_focus.context_uid,
                goal_focus.context_digest,
            ),
        )
    )
    ambient_bindings = tuple(
        (item.context_name, item.context_uid, item.context_digest)
        for item in prepared.target_context.local_contexts
    )
    all_source_bindings = tuple(
        dict.fromkeys((*source_bindings, *goal_bindings, *ambient_bindings))
    )
    with authorized_frozen_makemore_target(
        store,
        prepared.target_context,
        revalidate_after=False,
        required_granted_permissions=GRANTED_MAKEMORE_ADD_PERMISSIONS,
    ):
        return memorize_semantic_result(
            store=store,
            operation="makemore",
            source_name=source.context_name if source is not None else None,
            target=prepared.target,
            contents=contents,
            source_bindings=all_source_bindings,
            operation_args={
                "version": 5,
                **makemore_checkpoint_payload(prepared.result),
            },
            description=(
                f"Added {len(contents)} Makemore "
                f"{'Rules' if analysis.mode is MakemoreMode.GOAL_TO_RULES else 'Cases'} "
                f"to '{prepared.target.context_name}'"
            ),
        )


__all__ = [
    "MakemoreContextRole",
    "FrozenMakemoreSource",
    "PreparedMakemoreAdd",
    "apply_prepared_makemore_add",
    "freeze_makemore_context_source",
    "makemore_checkpoint_payload",
    "makemore_result_contents",
    "prepare_makemore_add",
    "prepare_makemore_add_to_frozen_target",
]
